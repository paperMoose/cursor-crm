import os
import re
import argparse # Added for command-line arguments
from datetime import datetime, timedelta # Added timedelta

# Define base directories
ACTIVE_LEADS_DIR = "active_leads"
PROJECTS_DIR = "projects"
PEOPLE_DIR = "people" # Added PEOPLE_DIR
ARCHIVE_SUBDIR = "archive"
DONE_SUBDIR = "done"
STALE_THRESHOLD_DAYS = 7

def get_md_files(directory_path, exclude_subdir_name=None):
    """
    Scans a directory for .md files, optionally excluding a specific subdirectory.

    Args:
        directory_path (str): The path to the directory to scan.
        exclude_subdir_name (str, optional): The name of a subdirectory to exclude. Defaults to None.

    Returns:
        list: A list of full paths to .md files.
    """
    md_files = []
    if not os.path.isdir(directory_path):
        # print(f"Warning: Directory not found: {directory_path}") # Optional warning
        return md_files
    for root, dirs, files in os.walk(directory_path):
        if exclude_subdir_name and exclude_subdir_name in dirs:
            dirs.remove(exclude_subdir_name)  # Don't traverse into the excluded subdirectory

        for file in files:
            if file.endswith(".md"):
                md_files.append(os.path.join(root, file))
    return md_files

def extract_field(content_block, field_name):
    """Extracts a specific field value from a Markdown status block using regex."""
    # Regex to find "- **Field Name:** Value" and capture "Value"
    # It handles potential leading/trailing whitespace around the value.
    match = re.search(r"- \*\*" + re.escape(field_name) + r":\*\*\s*(.*)", content_block, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/A"

def parse_date_string(date_str):
    """Attempts to parse a date string from common formats into a datetime.date object."""
    if not date_str or date_str.lower() == "n/a":
        return None

    # If multiple dates indicated by '->', take the last one.
    if "->" in date_str:
        date_str = date_str.split("->")[-1]

    # Clean common markdown like **
    date_str = date_str.replace("**", "").strip()

    # Define common date formats to try
    date_formats = [
        "%Y-%m-%d",      # e.g., 2025-05-09
        "%B %d, %Y",     # e.g., May 9, 2025
        "%b %d, %Y",      # e.g., Mar 9, 2025
        "%m/%d/%Y",      # e.g., 05/09/2025
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None # Could not parse with any known format

def parse_status_block(file_content, file_type):
    """
    Parses the ## Status block from the file content.

    Args:
        file_content (str): The entire content of the Markdown file.
        file_type (str): Either "lead" or "project".

    Returns:
        dict: A dictionary containing the extracted status fields.
    """
    status_data = {}
    # Regex to find the "## Status" section and capture everything until the next ## heading or end of file
    status_block_match = re.search(r"## Status\s*\n(.*?)(?=\n## |\Z)", file_content, re.DOTALL | re.IGNORECASE)

    if not status_block_match:
        status_data["Error"] = "Status block not found"
        status_data["LastUpdatedDateObj"] = None
        status_data["Last Updated"] = "N/A"
        return status_data

    status_block_content = status_block_match.group(1)

    if file_type == "lead":
        status_data["Stage"] = extract_field(status_block_content, "Stage")
        status_data["Next Step"] = extract_field(status_block_content, "Next Step")
        # status_data["Last Updated"] = extract_field(status_block_content, "Last Updated") # Keep common one below
        status_data["Reason (if Archived)"] = extract_field(status_block_content, "Reason (if Archived)")
    elif file_type == "project":
        status_data["Current Status"] = extract_field(status_block_content, "Current Status")
        status_data["Next Milestone"] = extract_field(status_block_content, "Next Milestone")
        status_data["Due Date"] = extract_field(status_block_content, "Due Date")
        status_data["Completion Date (if Done)"] = extract_field(status_block_content, "Completion Date (if Done)")
        # status_data["Last Updated"] = extract_field(status_block_content, "Last Updated") # Keep common one below
    
    last_updated_str = extract_field(status_block_content, "Last Updated")
    status_data["Last Updated"] = last_updated_str
    status_data["LastUpdatedDateObj"] = parse_date_string(last_updated_str)

    return status_data

def dump_directory_content(directory_path, dir_identifier_for_message, exclude_subdir_name=None):
    """Prints the content of all .md files in a directory."""
    md_files = get_md_files(directory_path, exclude_subdir_name=exclude_subdir_name)
    
    # Special handling for people directory as it has no subdirs to exclude by default
    if dir_identifier_for_message == "people" and exclude_subdir_name is not None:
         # This logic might need adjustment if people dir ever has subdirs to exclude by default
        pass # Currently, get_md_files for people dir doesn't take exclude_subdir_name

    if not md_files:
        if exclude_subdir_name and dir_identifier_for_message != "people":
            print(f"No .md files found in '{directory_path}' (excluding '{exclude_subdir_name}').")
        else:
            print(f"No .md files found in '{directory_path}'.")
        return

    for file_path in md_files:
        relative_path = os.path.relpath(file_path)
        print(f"\n--- START FILE: {relative_path} ---\n")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                print(f.read())
        except Exception as e:
            print(f"Error reading file {relative_path}: {e}")
        print(f"\n--- END FILE: {relative_path} ---\n")

def main():
    parser = argparse.ArgumentParser(description="Report status of active leads and projects, or dump their content.")
    parser.add_argument("--dump-content", choices=["leads", "projects", "people"], # Added "people"
                        help="Specify 'leads', 'projects', or 'people' to dump .md file content from the respective directory.")
    
    args = parser.parse_args()

    if args.dump_content:
        if args.dump_content == "leads":
            print(f"Dumping content from '{ACTIVE_LEADS_DIR}' directory (excluding '{ARCHIVE_SUBDIR}')...")
            dump_directory_content(ACTIVE_LEADS_DIR, "leads", exclude_subdir_name=ARCHIVE_SUBDIR)
        elif args.dump_content == "projects":
            print(f"Dumping content from '{PROJECTS_DIR}' directory (excluding '{DONE_SUBDIR}')...")
            dump_directory_content(PROJECTS_DIR, "projects", exclude_subdir_name=DONE_SUBDIR)
        elif args.dump_content == "people":
            print(f"Dumping content from '{PEOPLE_DIR}' directory...")
            dump_directory_content(PEOPLE_DIR, "people") # People dir typically has no subdirs like archive/done
        return # Exit after dumping content

    # --- Original status reporting logic ---
    all_statuses = []
    today = datetime.now().date()

    # Process active leads (excluding archive)
    lead_files = get_md_files(ACTIVE_LEADS_DIR, exclude_subdir_name=ARCHIVE_SUBDIR)
    for file_path in lead_files:
        status_item = {"File": os.path.relpath(file_path), "Type": "Active Lead"}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            parsed_data = parse_status_block(content, "lead")
            status_item.update(parsed_data)

            last_updated_obj = status_item.get("LastUpdatedDateObj")
            if last_updated_obj:
                age = (today - last_updated_obj).days
                if age > STALE_THRESHOLD_DAYS:
                    status_item["Staleness"] = f">{STALE_THRESHOLD_DAYS}d old"
                else:
                    status_item["Staleness"] = "Current"
            else:
                status_item["Staleness"] = "No Date"
        except Exception as e:
            status_item["Error"] = str(e)
            status_item["Staleness"] = "N/A"
        all_statuses.append(status_item)

    # Process projects (excluding done)
    project_files = get_md_files(PROJECTS_DIR, exclude_subdir_name=DONE_SUBDIR)
    for file_path in project_files:
        status_item = {"File": os.path.relpath(file_path), "Type": "Project"}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            parsed_data = parse_status_block(content, "project")
            status_item.update(parsed_data)

            last_updated_obj = status_item.get("LastUpdatedDateObj")
            if last_updated_obj:
                age = (today - last_updated_obj).days
                if age > STALE_THRESHOLD_DAYS:
                    status_item["Staleness"] = f">{STALE_THRESHOLD_DAYS}d old"
                else:
                    status_item["Staleness"] = "Current"
            else:
                status_item["Staleness"] = "No Date"
        except Exception as e:
            status_item["Error"] = str(e)
            status_item["Staleness"] = "N/A"
        all_statuses.append(status_item)
    
    # --- Output Formatting ---
    print(f"Status Report - {today.strftime('%Y-%m-%d')}\n")

    if not all_statuses:
        print("No active leads or projects found in specified directories.")
        return

    # Define a preferred order of columns. Others will be appended alphabetically.
    preferred_headers = [
        "File", "Type", "Staleness", "Stage", "Current Status", 
        "Next Step", "Next Milestone", "Last Updated", "Due Date", 
        "Completion Date (if Done)", "Reason (if Archived)", "Error"
    ]
    
    # Get all unique keys from all_statuses to form the full header list
    all_keys_found = set()
    for item in all_statuses:
        all_keys_found.update(item.keys())
    
    # Start with preferred headers that actually exist in the data
    final_headers = [h for h in preferred_headers if h in all_keys_found]
    # Add any other keys found in data that are not in preferred_headers, sorted alphabetically
    for key in sorted(list(all_keys_found)):
        if key not in final_headers and key != "LastUpdatedDateObj": # Exclude helper field
            final_headers.append(key)

    # Calculate column widths dynamically
    col_widths = {header: len(header) for header in final_headers} # Initialize with header lengths
    for item in all_statuses:
        for header in final_headers:
            col_widths[header] = max(col_widths[header], len(str(item.get(header, ""))))

    # Print header
    header_row_parts = []
    for header in final_headers:
        header_row_parts.append(header.ljust(col_widths[header]))
    header_row = " | ".join(header_row_parts)
    print(header_row)
    print("-" * len(header_row))

    # Print data rows
    for item in all_statuses:
        row_parts = []
        for header in final_headers:
            value = str(item.get(header, "")) # Use empty string for missing values for cleaner table
            row_parts.append(value.ljust(col_widths[header]))
        print(" | ".join(row_parts))

if __name__ == "__main__":
    main() 