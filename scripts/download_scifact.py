import os
import urllib.request
import zipfile

URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
ZIP_PATH = "scifact.zip"
EXTRACT_DIR = "data"

def download_and_extract():
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

    print(f"[*] Downloading BEIR SciFact dataset from {URL}...")
    urllib.request.urlretrieve(URL, ZIP_PATH)
    print("[+] Download complete.")

    print(f"[*] Extracting {ZIP_PATH} to {EXTRACT_DIR}/...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    print("[+] Extraction complete.")

    print(f"[*] Cleaning up {ZIP_PATH}...")
    os.remove(ZIP_PATH)
    print("[+] Done.")

if __name__ == "__main__":
    download_and_extract()
