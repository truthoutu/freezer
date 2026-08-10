use crate::extractor::{Extractor, RawContact};
use rand::seq::SliceRandom;
use reqwest::{Client, Proxy};
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::{mpsc, Semaphore};

#[derive(Clone, Debug)]
pub struct ProxyInfo {
    pub host: String,
    pub port: u16,
    pub user: String,
    pub pass: String,
}

impl ProxyInfo {
    pub fn parse_line(line: &str) -> Option<Self> {
        let parts: Vec<&str> = line.trim().split(':').collect();
        if parts.len() == 4 {
            let host = parts[0].to_string();
            let port = parts[1].parse::<u16>().ok()?;
            let user = parts[2].to_string();
            let pass = parts[3].to_string();
            Some(ProxyInfo { host, port, user, pass })
        } else {
            None
        }
    }

    pub fn to_socks5_url(&self) -> String {
        format!("socks5://{}:{}@{}:{}", self.user, self.pass, self.host, self.port)
    }
}

pub struct CrawlerConfig {
    pub start_urls: Vec<String>,
    pub max_depth: usize,
    pub max_concurrency: usize,
    pub user_agent: String,
    pub proxy_file: Option<PathBuf>,
}

pub struct Crawler {
    config: CrawlerConfig,
    proxies: Vec<ProxyInfo>,
}

impl Crawler {
    pub fn new(config: CrawlerConfig) -> Self {
        let mut proxies = Vec::new();
        if let Some(ref path) = config.proxy_file {
            if let Ok(content) = fs::read_to_string(path) {
                for line in content.lines() {
                    if let Some(p) = ProxyInfo::parse_line(line) {
                        proxies.push(p);
                    }
                }
            }
        }

        Self { config, proxies }
    }

    fn build_client_for_proxy(&self, proxy_info: Option<&ProxyInfo>) -> Client {
        let mut builder = Client::builder()
            .user_agent(&self.config.user_agent)
            .timeout(std::time::Duration::from_secs(12))
            .danger_accept_invalid_certs(true);

        if let Some(p) = proxy_info {
            let socks_url = p.to_socks5_url();
            if let Ok(proxy) = Proxy::all(&socks_url) {
                builder = builder.proxy(proxy);
            }
        }

        builder.build().unwrap_or_else(|_| Client::new())
    }

    pub async fn run(&self) -> Vec<RawContact> {
        let (tx, mut rx) = mpsc::channel::<(String, usize)>(1000);
        let (contact_tx, mut contact_rx) = mpsc::channel::<Vec<RawContact>>(1000);

        let semaphore = Arc::new(Semaphore::new(self.config.max_concurrency));
        let mut visited = HashSet::new();

        for url in &self.config.start_urls {
            if visited.insert(url.clone()) {
                let _ = tx.send((url.clone(), 0)).await;
            }
        }

        let extractor = Arc::new(Extractor::new());
        let max_depth = self.config.max_depth;
        let proxies = self.proxies.clone();

        tokio::spawn(async move {
            while let Some((url_str, depth)) = rx.recv().await {
                if depth > max_depth {
                    continue;
                }

                let sem = semaphore.clone();
                let extractor_clone = extractor.clone();
                let contact_tx_clone = contact_tx.clone();
                let user_agent = "Mozilla/5.0".to_string();

                // Pick random proxy if available
                let proxy_choice = if !proxies.is_empty() {
                    let mut rng = rand::thread_rng();
                    proxies.choose(&mut rng).cloned()
                } else {
                    None
                };

                tokio::spawn(async move {
                    let _permit = sem.acquire().await;
                    
                    // Build client directly in the spawned task
                    let mut client_builder = Client::builder()
                        .user_agent(&user_agent)
                        .timeout(std::time::Duration::from_secs(30))
                        .danger_accept_invalid_certs(true);
                    
                    if let Some(p) = proxy_choice.as_ref() {
                        let socks_url = p.to_socks5_url();
                        if let Ok(proxy) = Proxy::all(&socks_url) {
                            client_builder = client_builder.proxy(proxy);
                        }
                    }
                    
                    let client = client_builder.build().unwrap_or_else(|_| Client::new());
                    
                    // Retry logic with exponential backoff
                    for attempt in 0..3 {
                        if attempt > 0 {
                            tokio::time::sleep(std::time::Duration::from_secs(2_u64.pow(attempt))).await;
                        }
                        
                        match client.get(&url_str).send().await {
                            Ok(resp) => {
                                if resp.status().is_success() {
                                    match resp.text().await {
                                        Ok(html) => {
                                            let contacts = extractor_clone.extract_contacts(&html, &url_str);
                                            if !contacts.is_empty() {
                                                let _ = contact_tx_clone.send(contacts).await;
                                            }
                                            break; // Success, exit retry loop
                                        }
                                        Err(e) => {
                                            eprintln!("[Attempt {}] Failed to read response body for {}: {}", attempt + 1, url_str, e);
                                        }
                                    }
                                } else {
                                    eprintln!("[Attempt {}] HTTP {} for {}", attempt + 1, resp.status(), url_str);
                                }
                            }
                            Err(e) => {
                                eprintln!("[Attempt {}] Request failed for {}: {}", attempt + 1, url_str, e);
                            }
                        }
                    }
                });
            }
        });

        let mut all_contacts = Vec::new();
        // Increased timeout to 120 seconds for real web requests
        let timeout = tokio::time::sleep(tokio::time::Duration::from_secs(120));
        tokio::pin!(timeout);

        loop {
            tokio::select! {
                Some(contacts) = contact_rx.recv() => {
                    all_contacts.extend(contacts);
                }
                _ = &mut timeout => {
                    break;
                }
            }
        }

        all_contacts
    }
}
