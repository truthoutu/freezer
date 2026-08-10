"""
Intelligence & Data Cleaning Layer for 'The Harvester'
Normalizes international phone numbers (US, CA, AU, CH, DE), rejects IP addresses,
dedupes contacts, infers gender heuristics (multilingual), filters by occupation/country, and exports reports.
"""

import json
import logging
import re
import sys
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import gender_guesser.detector as gender
    GENDER_DETECTOR = gender.Detector(case_sensitive=False)
except ImportError:
    GENDER_DETECTOR = None


class CleanerPipeline:
    def __init__(self, raw_data_path: Path):
        self.raw_data_path = Path(raw_data_path)
        self.df = pd.DataFrame()

    def load_data(self) -> bool:
        if not self.raw_data_path.exists():
            logging.warning(f"Raw data file {self.raw_data_path} does not exist.")
            return False

        try:
            with open(self.raw_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data or not isinstance(data, list):
                logging.warning("Raw dataset is empty or invalid JSON structure.")
                return False

            self.df = pd.DataFrame(data)
            return True
        except Exception as e:
            logging.error(f"Failed to load raw JSON data: {e}")
            return False

    def normalize_phone_and_detect_country(self, phone: str) -> tuple[str, str]:
        if not phone or not isinstance(phone, str):
            return "", "Unknown"

        phone_clean = phone.strip()

        # Reject IPv4 addresses (e.g. 45.38.107.97)
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", phone_clean):
            return "", "Invalid (IP Address)"

        digits = re.sub(r"\D", "", phone_clean)

        # Require between 7 and 15 digits
        if len(digits) < 7 or len(digits) > 15:
            return "", "Invalid Format"

        # Detect Country & Format Phone
        if phone_clean.startswith("+61") or (digits.startswith("61") and len(digits) >= 10):
            d = digits[2:] if digits.startswith("61") else digits
            return f"+61 {d[:1]} {d[1:5]} {d[5:]}", "Australia"

        elif phone_clean.startswith("+41") or (digits.startswith("41") and len(digits) >= 9):
            d = digits[2:] if digits.startswith("41") else digits
            return f"+41 {d[:2]} {d[2:5]} {d[5:]}", "Switzerland"

        elif phone_clean.startswith("+49") or (digits.startswith("49") and len(digits) >= 10):
            d = digits[2:] if digits.startswith("49") else digits
            return f"+49 {d[:3]} {d[3:]}", "Germany"

        elif len(digits) == 10:
            return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}", "United States / Canada"

        elif len(digits) == 11 and digits.startswith("1"):
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}", "United States / Canada"

        elif len(digits) >= 8:
            return f"+{digits}", "International"

        return "", "Invalid Format"

    def infer_gender(self, name: str, occupation: str = "") -> str:
        if occupation and isinstance(occupation, str):
            occ_lower = occupation.lower()
            if occ_lower.endswith("in") or "frau" in occ_lower or "ms." in occ_lower or "mrs." in occ_lower:
                return "Female"

        if not name or not isinstance(name, str) or name in ["N/A", "Cloudflare Ray", "Cloudflare"]:
            return "Unknown"

        first_name = name.strip().split()[0]
        
        if GENDER_DETECTOR:
            try:
                res = GENDER_DETECTOR.get_gender(first_name)
                if res in ["female", "mostly_female"]:
                    return "Female"
                elif res in ["male", "mostly_male"]:
                    return "Male"
            except Exception:
                pass

        female_endings = ("a", "i", "ie", "lyn", "e", "elle", "ann", "ette", "ine", "isa", "ina")
        if first_name.lower().endswith(female_endings):
            return "Female (Inferred)"

        return "Unknown"

    def clean(self, target_occupation: str = None, filter_gender: str = None, filter_country: str = None) -> pd.DataFrame:
        if self.df.empty or "phone" not in self.df.columns:
            return pd.DataFrame()

        # Phone Normalization & Country Detection
        phone_info = self.df["phone"].apply(self.normalize_phone_and_detect_country)
        self.df["phone_normalized"] = [p[0] for p in phone_info]
        self.df["country_inferred"] = [p[1] for p in phone_info]

        # Filter out invalid phone numbers (IPs, empty)
        self.df = self.df[self.df["phone_normalized"].str.len() > 0]

        if self.df.empty:
            return pd.DataFrame()

        # Fill Missing Values & Clean Cloudflare names
        if "name" in self.df.columns:
            self.df["name"] = self.df["name"].fillna("N/A")
            self.df.loc[self.df["name"].str.contains("Cloudflare", case=False, na=False), "name"] = "N/A"
        else:
            self.df["name"] = "N/A"

        if "occupation_context" in self.df.columns:
            self.df["occupation_context"] = self.df["occupation_context"].fillna("General Professional")
        else:
            self.df["occupation_context"] = "General Professional"

        # Deduplicate by Phone Number
        self.df = self.df.drop_duplicates(subset=["phone_normalized"], keep="first")

        # Infer Gender
        self.df["gender_inferred"] = self.df.apply(
            lambda row: self.infer_gender(row["name"], row["occupation_context"]), axis=1
        )

        filtered = self.df.copy()

        # Apply Filters
        if target_occupation:
            filtered = filtered[filtered["occupation_context"].str.contains(target_occupation, case=False, na=False)]

        if filter_gender:
            filtered = filtered[filtered["gender_inferred"].str.contains(filter_gender, case=False, na=False)]

        if filter_country:
            filtered = filtered[filtered["country_inferred"].str.contains(filter_country, case=False, na=False)]

        # Safely add optional columns if they don't exist to prevent data loss
        final_cols = ["name", "occupation_context", "phone_normalized", "gender_inferred", "country_inferred", "source_url", "raw_snippet"]
        final_df = filtered.reindex(columns=final_cols, fill_value="").rename(columns={
            "name": "Name",
            "occupation_context": "Occupation",
            "phone_normalized": "Phone Number",
            "gender_inferred": "Gender (Inferred)",
            "country_inferred": "Country",
            "source_url": "Source URL",
            "raw_snippet": "Snippet Context"
        })

        return final_df

    def export(self, df: pd.DataFrame, output_prefix: Path):
        output_prefix = Path(output_prefix)
        csv_path = output_prefix.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        logging.info(f"Cleaned dataset exported to CSV: {csv_path}")

        try:
            excel_path = output_prefix.with_suffix(".xlsx")
            df.to_excel(excel_path, index=False)
            logging.info(f"Cleaned dataset exported to Excel: {excel_path}")
        except Exception as e:
            logging.warning(f"Skipping Excel export ({e}). Install openpyxl for .xlsx support.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python cleaner.py <raw_json_file> [output_prefix] [target_occupation] [filter_gender] [filter_country]")
        sys.exit(1)

    raw_json = Path(sys.argv[1])
    output_prefix = Path(sys.argv[2]) if len(sys.argv) > 2 else raw_json.with_name("harvested_contacts_cleaned")
    target_occ = sys.argv[3] if len(sys.argv) > 3 else None
    filter_gen = sys.argv[4] if len(sys.argv) > 4 else None
    filter_country = sys.argv[5] if len(sys.argv) > 5 else None

    cleaner = CleanerPipeline(raw_json)
    if cleaner.load_data():
        cleaned_df = cleaner.clean(target_occupation=target_occ, filter_gender=filter_gen, filter_country=filter_country)
        cleaner.export(cleaned_df, output_prefix)
        logging.info(f"Total records processed: {len(cleaned_df)}")


if __name__ == "__main__":
    main()
