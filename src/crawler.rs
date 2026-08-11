use crate::extractor::{Extractor, RawContact};
use rand::seq::SliceRandom;
use reqwest::{Client, Proxy};
use rusqlite::{Connection, Result};
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
    pub occupation: Option<String>,
    pub country: Option<String>,
    pub max_depth: usize,
    pub max_concurrency: usize,
    pub proxy_file: Option<PathBuf>,
}

/// Generates a diverse set of Google search dorks for a given occupation and country.
fn generate_dynamic_queries(occupation: &str, country: &str) -> Vec<String> {
    let occupation_query = format!("\"{}\"", occupation);
    let country_query = format!("\"{}\"", country);

    let mut domains = Vec::new();
    match country {
        "United States" | "Canada" => {
            domains.extend(vec![
                // Directories
                "yelp.com", "yellowpages.com", "whitepages.com", "angi.com", "houzz.com",
                "yellowpages.ca", "brownbook.net", "chamberofcommerce.com", "pagesjaunes.ca",
                // Niche & Professional
                "zocdoc.com", "avvo.com", "thumbtack.com", "linkedin.com", "crunchbase.com",
            ]);
        }
        "Germany" | "Switzerland" => {
            domains.extend(vec![
                // Directories
                "yellowpages.ch", "local.ch", "gelbeseiten.de", "herold.de", "dastelefonbuch.de",
                "kompass.com", "brownbook.net",
                // Professional
                "handelsregister.de", "linkedin.com", "xing.com",
            ]);
        }
        "Australia" => {
            domains.extend(vec![
                // Directories
                "yellowpages.com.au", "truelocal.com.au", "whitepages.com.au",
                "yellowpages.co.nz", "hotfrog.com.au", "localsearch.com.au",
            ]);
        }
        _ => { // Fallback to a general list if country doesn't match
            domains.extend(vec![
                "linkedin.com", "yellowpages.com", "yelp.com", "kompass.com", "brownbook.net"
            ]);
        }
    };

    let mut query_templates = Vec::new();
    for domain in domains {
        query_templates.push(format!("site:{} {} {} contact OR phone", domain, occupation_query, country_query));
    }

    // Add broader, non-site-specific queries to discover new sources
    query_templates.push(format!("\"{occupation}\" member directory {country_query}"));
    if country == "Australia" { // Add niche discovery for Australia as requested
        query_templates.push(format!("site:.com.au \"find a doctor\" OR \"health professionals\" list"));
    }

    query_templates.into_iter().map(|q| {
        format!("https://www.google.com/search?q={}", urlencoding::encode(&q))
    }).collect()
}

/// The Memory Vault: Fetches all existing phone numbers from the SQLite DB.
fn get_seen_phones_from_db(db_path: &PathBuf) -> Result<std::collections::HashSet<String>, rusqlite::Error> {
    let conn = Connection::open(db_path)?;
    let mut stmt = conn.prepare("SELECT phone FROM contact_leads")?;
    let phone_iter = stmt.query_map([], |row| {
        let phone: String = row.get(0)?;
        // Normalize to digits only for accurate deduplication
        Ok(phone.chars().filter(|c| c.is_digit(10)).collect::<String>())
    })?;

    let mut seen_phones = std::collections::HashSet::new();
    for phone in phone_iter {
        if let Ok(p) = phone {
            if !p.is_empty() {
                seen_phones.insert(p);
            }
        }
    }
    Ok(seen_phones)
}

/// Normalizes a phone number string to digits only.
fn normalize_phone(phone: &str) -> String {
    phone.chars().filter(|c| c.is_digit(10)).collect()
}

pub struct Crawler {
    config: CrawlerConfig,
    proxies: Vec<ProxyInfo>,
    user_agents: Vec<String>,
}

impl Crawler {
    pub async fn new(config: CrawlerConfig) -> Self {
        let mut proxies = Vec::new();
        let mut user_agents = Vec::new();

        // Fetch live user agents, with a fallback list
        let default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36".to_string();
        match reqwest::get("https://jnrbsn.github.io/user-agents/user-agents.json").await {
            Ok(resp) => {
                if let Ok(agents) = resp.json::<Vec<String>>().await {
                    user_agents = agents;
                }
            }
            Err(_) => {
                eprintln!("Could not fetch live user-agents, using default.");
            }
        };

        // If fetching failed or returned nothing, use a reliable default
        if user_agents.is_empty() {
            user_agents.push(default_ua);
        }

        if let Some(ref path) = config.proxy_file {
            if let Ok(content) = fs::read_to_string(path) {
                for line in content.lines() {
                    if let Some(p) = ProxyInfo::parse_line(line) {
                        proxies.push(p);
                    }
                }
            }
        }

        Self { config, proxies, user_agents }
    }

    pub async fn run(&self) -> Vec<RawContact> {
        let (tx, mut rx) = mpsc::channel::<(String, usize)>(1000);
        let (contact_tx, mut contact_rx) = mpsc::channel::<Vec<RawContact>>(1000);

        // Generate dynamic search queries if occupation and country are provided
        let initial_urls = if let (Some(occ), Some(country)) = (&self.config.occupation, &self.config.country) {
            generate_dynamic_queries(occ, country)
        } else {
            self.config.start_urls.clone()
        };

        // This HashSet is now local to the run method, which is cleaner.
        let mut visited = std::collections::HashSet::new();
        let semaphore = Arc::new(Semaphore::new(self.config.max_concurrency));

        for url in &initial_urls {
            let _ = tx.send((url.clone(), 0)).await;
        }

        let extractor = Arc::new(Extractor::new());
        let max_depth = self.config.max_depth;
        let proxies = self.proxies.clone();
        let user_agents = self.user_agents.clone();
        let visited = Arc::new(tokio::sync::Mutex::new(visited));

        tokio::spawn(async move {
            while let Some((url_str, depth)) = rx.recv().await {

                let sem = semaphore.clone();
                let extractor_clone = extractor.clone();
                let contact_tx_clone = contact_tx.clone();
                let tx_clone = tx.clone(); // Clone sender for recursive crawling
                let user_agents_clone = user_agents.clone();

                // CRITICAL FIX: Check if visited *before* spawning the task.
                // This prevents re-crawling and potential infinite loops.
                let mut visited_guard = visited.lock().await;
                if !visited_guard.insert(url_str.clone()) || depth > max_depth {
                    continue;
                }
                // Drop the guard to avoid holding the lock inside the spawned task
                drop(visited_guard);

                // Pick random proxy if available
                let proxy_choice = if !proxies.is_empty() {
                    let mut rng = rand::thread_rng();
                    proxies.choose(&mut rng).cloned()
                } else {
                    None
                };

                tokio::spawn(async move {
                    let _permit = sem.acquire().await;
                    
                    // Pick a random, up-to-date user-agent
                    let random_ua = user_agents_clone
                        .choose(&mut rand::thread_rng())
                        .cloned()
                        .unwrap_or_else(|| "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36".to_string());

                    // Build client directly in the spawned task
                    let mut client_builder = Client::builder()
                        .user_agent(random_ua)
                        .timeout(std::time::Duration::from_secs(30))
                        .danger_accept_invalid_certs(true);
                    
                    if let Some(p) = proxy_choice.as_ref() {
                        let socks_url = p.to_socks5_url();
                        if let Ok(proxy) = Proxy::all(&socks_url) {
                            client_builder = client_builder.proxy(proxy);
                        }
                    }
                    
                    let client = match client_builder.build() {
                        Ok(c) => c,
                        Err(e) => {
                            eprintln!("ERROR: Failed to build HTTP client for {}: {}. Aborting task.", url_str, e);
                            return; // Exit this spawned task
                        }
                    };
                    
                    // Retry logic with exponential backoff (3 attempts) for network resilience
                    for attempt in 0..3 {
                        if attempt > 0 {
                            tokio::time::sleep(std::time::Duration::from_secs(2_u64.pow(attempt))).await;
                        }
                        
                        match client.get(&url_str).send().await {
                            Ok(resp) => { // Smart Pivot: Detect 403/429 and log, but don't stall
                                if resp.status().is_success() { 
                                    match resp.text().await {
                                        Ok(html) => {
                                            let contacts = extractor_clone.extract_contacts(&html, &url_str);
                                            if !contacts.is_empty() {
                                                let _ = contact_tx_clone.send(contacts).await;
                                            }

                                            // Crawl deeper: find new links and send them to the queue
                                            if depth < max_depth {
                                                let new_links = extractor_clone.extract_links(&html, &url_str);
                                                for new_link in new_links {
                                                    // Send to the channel to be processed by the receiver loop
                                                    let _ = tx_clone.send((new_link, depth + 1)).await;
                                                }
                                            }

                                            break; // Success, exit retry loop
                                        }
                                        Err(e) => {
                                            eprintln!("[Attempt {}] Failed to read response body for {}: {}", attempt + 1, url_str, e);
                                        }
                                    }
                                } else {
                                    if resp.status().as_u16() == 403 {
                                        eprintln!("[Attempt {}] 🚫 403 Forbidden for {}. Pivoting to next task.", attempt + 1, url_str);
                                    } else if resp.status().as_u16() == 429 {
                                        eprintln!("[Attempt {}] ⏳ 429 Too Many Requests for {}. Pivoting to next task.", attempt + 1, url_str);
                                    }
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

        // MEMORY VAULT: Deduplicate against the main SQLite database AT THE SOURCE.
        let db_path = PathBuf::from("harvest_history.db");
        if db_path.exists() {
            match get_seen_phones_from_db(&db_path) {
                Ok(seen_phones) => {
                    let initial_count = all_contacts.len();
                    all_contacts.retain(|contact| {
                        let normalized_phone = normalize_phone(&contact.phone);
                        !normalized_phone.is_empty() && !seen_phones.contains(&normalized_phone)
                    });
                    eprintln!("[Memory Vault] Deduplicated at source: {} fresh contacts remain out of {}.", all_contacts.len(), initial_count);
                }
                Err(e) => eprintln!("[Memory Vault] Error: Could not deduplicate from DB at source: {}", e),
            }
        }

        all_contacts
    }
}
