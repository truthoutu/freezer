mod crawler;
mod extractor;

use clap::Parser;
use crawler::{Crawler, CrawlerConfig};
use extractor::{Extractor, RawContact};
use std::fs;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(author, version, about = "High speed contact data harvester engine in Rust", long_about = None)]
struct Args {
    /// Seed URLs to crawl
    #[arg(short, long, value_delimiter = ',')]
    urls: Vec<String>,

    /// HTML files to parse directly (offline mode)
    #[arg(short, long, value_delimiter = ',')]
    files: Vec<PathBuf>,

    /// Path to proxies.txt file (IP:Port:User:Pass format)
    #[arg(short, long)]
    proxies: Option<PathBuf>,

    /// Max crawling depth
    #[arg(short, long, default_value_t = 1)]
    depth: usize,

    /// Max concurrent requests
    #[arg(short, long, default_value_t = 10)]
    concurrency: usize,

    /// Output JSON path
    #[arg(short, long)]
    output: Option<PathBuf>,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    let mut all_contacts: Vec<RawContact> = Vec::new();

    let extractor = Extractor::new();

    // 1. Process local HTML files directly if provided
    for file_path in &args.files {
        if let Ok(content) = fs::read_to_string(file_path) {
            let path_str = file_path.to_string_lossy().to_string();
            let contacts = extractor.extract_contacts(&content, &path_str);
            all_contacts.extend(contacts);
        }
    }

    // 2. Process web URLs if provided with SOCKS5 Proxy rotation
    if !args.urls.is_empty() {
        let config = CrawlerConfig {
            start_urls: args.urls,
            max_depth: args.depth,
            max_concurrency: args.concurrency,
            user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36".to_string(),
            proxy_file: args.proxies,
        };

        let crawler = Crawler::new(config);
        let crawled_contacts = crawler.run().await;
        all_contacts.extend(crawled_contacts);
    }

    let json_output = serde_json::to_string_pretty(&all_contacts).unwrap_or_else(|_| "[]".to_string());

    if let Some(output_path) = args.output {
        let _ = fs::write(&output_path, &json_output);
        println!("Harvested {} contacts -> saved to {}", all_contacts.len(), output_path.display());
    } else {
        println!("{}", json_output);
    }
}
