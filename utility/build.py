#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
import tempfile
import zipfile
from dotenv import load_dotenv

try:
    from utility.crawl import crawl_site
except ImportError:
    from crawl import crawl_site

def compile_index(src_dir, temp_index_dir):
    """Loads markdown files from src_dir, runs embeddings, and saves FAISS index to temp_index_dir."""
    print("Loading dependencies for vector index generation...")
    try:
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        print("Error: Required libraries not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)

    print(f"Reading Markdown files from: {src_dir}")
    loader = DirectoryLoader(src_dir, glob="**/*.md", loader_cls=TextLoader)
    docs = loader.load()
    if not docs:
        print(f"Error: No Markdown (.md) files found in {src_dir}.")
        sys.exit(1)

    print(f"Loaded {len(docs)} document file(s). Splitting into semantic chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    print(f"Generated {len(chunks)} text chunks.")

    print("Generating vector embeddings and building FAISS index...")
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(chunks, embeddings)
    
    os.makedirs(temp_index_dir, exist_ok=True)
    db.save_local(temp_index_dir)
    print(f"FAISS index compiled successfully in temporary storage: {os.listdir(temp_index_dir)}")

def zip_directory(folder_path, zip_file_path):
    """Zips the contents of a folder recursively, ensuring the root files are at the top level of the zip."""
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Map paths relative to the folder_path root
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)

def build_package(src_dir, out_zip):
    # Normalize paths
    src_dir = os.path.abspath(src_dir)
    out_zip = os.path.abspath(out_zip)

    if not os.path.exists(src_dir) or not os.path.isdir(src_dir):
        print(f"Error: Source directory '{src_dir}' does not exist or is not a directory.")
        sys.exit(1)

    # 1. Load the client's .env from their directory to get API keys
    src_env = os.path.join(src_dir, ".env")
    if not os.path.exists(src_env):
        print(f"Error: A config file (.env) must exist in the source directory: {src_env}")
        sys.exit(1)
    
    load_dotenv(src_env)
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is not set in the source directory's .env file.")
        sys.exit(1)

    # 2. Create a temporary folder to assemble the deployable bundle
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Assembling package in temporary directory...")

        # A. Copy core code (main.py and src/) directly to the root of temp_dir
        core_dir = "core"
        if not os.path.exists(core_dir):
            print(f"Error: Core directory '{core_dir}' not found. Make sure you run this from the project root.")
            sys.exit(1)

        # Copy main.py to root of temp_dir
        shutil.copy(os.path.join(core_dir, "main.py"), os.path.join(temp_dir, "main.py"))
        # Copy core/src/ to temp_dir/src/
        shutil.copytree(os.path.join(core_dir, "src"), os.path.join(temp_dir, "src"), dirs_exist_ok=True)
        print("Copied runtime core code and modules.")

        # B. Copy requirements.txt to root of temp_dir
        if os.path.exists("requirements.txt"):
            shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))
            print("Copied requirements.txt.")

        # C. Copy the tenant's .env configuration to the root of temp_dir
        shutil.copy(src_env, os.path.join(temp_dir, ".env"))
        print("Copied tenant configuration (.env).")

        # D. Compile vector index directly into temp_dir/index/
        temp_index_dir = os.path.join(temp_dir, "index")
        compile_index(src_dir, temp_index_dir)

        # E. Zip the temporary directory
        os.makedirs(os.path.dirname(out_zip), exist_ok=True)
        print(f"Compressing files into deployment ZIP: {out_zip}...")
        zip_directory(temp_dir, out_zip)

    print(f"\nSuccessfully compiled and packaged standalone deployable ZIP!")
    print(f"Bundle output: {out_zip}")
    print("\nTo deploy this package on your target VPS:")
    print("1. Upload the ZIP file and extract it.")
    print("2. Run: pip install -r requirements.txt")
    print("3. Start the bot directly using: python main.py")

def init_workspace(init_dir, url=None):
    init_dir = os.path.abspath(init_dir)
    print(f"Initializing new client configuration workspace at: {init_dir}")
    os.makedirs(init_dir, exist_ok=True)

    # 1. Copy .env.example to .env inside target folder
    env_example = ".env.example"
    env_target = os.path.join(init_dir, ".env")
    if os.path.exists(env_example):
        shutil.copy(env_example, env_target)
        print(f"Created config template: {env_target}")
    else:
        # Fallback if run from a subfolder
        parent_env_example = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.example")
        if os.path.exists(parent_env_example):
            shutil.copy(parent_env_example, env_target)
            print(f"Created config template: {env_target}")
        else:
            print("Warning: .env.example template not found. Please create .env manually.")

    # 2. Populate Workspace Data
    if url:
        # Normalize target URL
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        print(f"\n🕸️ Web crawl URL provided: {url}")
        print("Running site crawler to seed the workspace Markdown files...")
        crawl_site(url, init_dir, max_pages=15, max_depth=2)
    else:
        # Create default placeholders
        # Create sample visitor policy
        sample_policy = os.path.join(init_dir, "visitor_policy.md")
        with open(sample_policy, "w") as f:
            f.write("# Visitor Policy\n\nWelcome! Please check in at reception. Wi-Fi: Office-Guest / WelcomeFrontDesk2026")
        print(f"Created sample policy doc: {sample_policy}")

        # Create sample FAQ
        sample_faq = os.path.join(init_dir, "faq.md")
        with open(sample_faq, "w") as f:
            f.write("# Frequently Asked Questions\n\n## Where is the restroom?\nIt is located down the main hall on the left. Code: 2468#")
        print(f"Created sample FAQ doc: {sample_faq}")

    print(f"\nSuccessfully initialized workspace '{os.path.basename(init_dir)}'!")
    print("Next steps:")
    print(f"1. Open and fill in the API keys in: {env_target}")
    print(f"2. Verify or add policy documents (.md) inside: {init_dir}")
    print(f"3. Build and package the ZIP using:")
    print(f"   python3 utility/build.py --src {init_dir} --out dist/deploy_{os.path.basename(init_dir)}.zip")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Front Desk Bot Compiler & Packager")
    parser.add_argument("--init", help="Path to initialize a new client configuration directory")
    parser.add_argument("--url", help="Optional website URL to crawl and seed the workspace (use alongside --init)")
    parser.add_argument("--src", help="Path to the tenant's local directory containing .env and markdown files")
    parser.add_argument("--out", help="Path to save the generated deployable ZIP file (e.g. dist/haircuts.zip)")

    args = parser.parse_args()

    if args.init:
        init_workspace(args.init, args.url)
    elif args.src and args.out:
        build_package(args.src, args.out)
    else:
        parser.print_help()
        print("\nError: Please provide either --init <path> to generate template files, OR both --src <path> and --out <path> to compile a package.")
        sys.exit(1)

