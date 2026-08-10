"""
Master Runner Script for The Harvester Hybrid Pipeline
Orchestrates Rust scraper execution and feeds raw harvest into Python intelligence cleaner.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="The Harvester - Hybrid Rust/Python Scraper & Cleaner Pipeline")
    parser.add_argument("--urls", "-u", nargs="+", help="Target URLs to crawl")
    parser.add_argument("--files", "-f", nargs="+", help="Local HTML file paths to parse")
    parser.add_argument("--depth", "-d", type=int, default=1, help="Crawl depth")
    parser.add_argument("--concurrency", "-c", type=int, default=10, help="Concurrency limit")
    parser.add_argument("--proxies", "-p", help="Path to proxies.txt file")
    parser.add_argument("--occupation", "-o", help="Target occupation filter (e.g. Nurse, Realtor)")
    parser.add_argument("--gender", "-g", help="Gender filter (e.g. Female, Male)")
    parser.add_argument("--country", "-ct", help="Country filter (e.g. Germany, Switzerland, Australia, United States)")
    parser.add_argument("--output", "-out", default="final_harvest", help="Output file prefix (without extension)")

    args = parser.parse_args()

    project_root = Path(__file__).parent.resolve()
    cargo_cmd = ["cargo", "run", "--release", "--"]

    cmd = cargo_cmd.copy()

    if args.urls:
        cmd.extend(["--urls", ",".join(args.urls)])
    if args.files:
        cmd.extend(["--files", ",".join(args.files)])
    if args.proxies:
        cmd.extend(["--proxies", args.proxies])
    
    cmd.extend(["--depth", str(args.depth)])
    cmd.extend(["--concurrency", str(args.concurrency)])

    raw_json_out = project_root / "raw_harvest.json"
    cmd.extend(["--output", str(raw_json_out)])

    print("[*] Launching Rust Harvester Engine...")
    res = subprocess.run(cmd, cwd=project_root)
    if res.returncode != 0:
        print("[!] Rust engine returned non-zero exit code. Building crate first...")
        build_res = subprocess.run(["cargo", "build", "--release"], cwd=project_root)
        if build_res.returncode != 0:
            print("[!] Cargo build failed.")
            sys.exit(1)
        res = subprocess.run(cmd, cwd=project_root)

    print("\n[*] Rust harvesting complete. Launching Python Intelligence Layer...")
    cleaner_script = project_root / "cleaner.py"
    output_prefix = project_root / args.output

    clean_cmd = [sys.executable, str(cleaner_script), str(raw_json_out), str(output_prefix)]
    if args.occupation:
        clean_cmd.append(args.occupation)
    if args.gender:
        clean_cmd.append(args.gender)
    if args.country:
        clean_cmd.append(args.country)

    subprocess.run(clean_cmd, cwd=project_root)
    print("\n[+] Pipeline execution completed successfully!")


if __name__ == "__main__":
    main()
