# itty-bitty-blog

An ultra-efficient, minimalist Static Site Generator in Python.

## Overview

**itty-bitty-blog** is designed for high performance on low-resource hardware like the Raspberry Pi Zero. It converts Markdown files into a static HTML website with zero client-side JavaScript and a single embedded CSS block.

### Features

*   **Flat-File Architecture**: No database. Content lives in `posts/` as Markdown files.
*   **Dependency-Free**: Uses standard Python libraries. No `pip install` required for basic usage.
*   **Ultra-Lightweight**: Generator code is < 10KB. Output pages are tiny.
*   **Performance**: Builds 50+ posts in milliseconds.
*   **Valid HTML5**: Clean, semantic markup.

## Setup

1.  Clone this repository or copy the files to your machine.
2.  Ensure you have Python 3 installed.

```bash
python3 --version
```

## Usage

1.  **Create Content**: Add your Markdown files to the `posts/` directory.
    *   Files must have a YAML frontmatter block at the top:
        ```markdown
        ---
        title: My Post Title
        date: 2023-10-27
        category: General
        ---
        ```
    *   The rest of the file is your content. Supported Markdown features:
        *   Headers (`#`, `##`, etc.)
        *   Lists (`-` for unordered, `1.` for ordered)
        *   Bold (`**text**`) and Italic (`*text*`)
        *   Links (`[text](url)`)
        *   Images (`![alt](url)`)
        *   Code blocks (` ``` `)
        *   Blockquotes (`>`)

2.  **Build the Site**: Run the build script.

```bash
python3 build.py
```

3.  **Deploy**: The output is generated in the `dist/` folder.
    *   Copy the contents of `dist/` to your web server root (e.g., `/var/www/html/` or via SFTP).
    *   Since it's static HTML, it works with Nginx, Apache, GitHub Pages, Netlify, etc.

## Customization

*   **Site Title & Author**: Edit the configuration variables at the top of `build.py`.
*   **Layout & CSS**: Modify `templates/layout.html`.
    *   CSS is embedded in the `<head>` to minimize HTTP requests.
    *   Placeholder links for "GitHub" and "Resume" are in the `<nav>` section, hidden by `class="hidden"`. Remove the class to show them.

## Requirements

*   Python 3.6+
*   No external Python packages required.

## License

MIT
