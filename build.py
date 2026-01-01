#!/usr/bin/env python3
import os
import re
import shutil
import sys
import time
from string import Template
from datetime import datetime

# Configuration
POSTS_DIR = 'posts'
TEMPLATES_DIR = 'templates'
DIST_DIR = 'dist'
SITE_TITLE = "My Itty Bitty Blog"
AUTHOR_NAME = "Jules"

def parse_markdown(text):
    """
    A minimal Markdown parser using standard library `re`.
    Supports headers, bold, italic, links, lists, code blocks, blockquotes.
    """
    # Escape HTML characters (basic)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 1. Protect Code Blocks
    code_blocks = {}
    def save_code_block(match):
        key = f"__CODEBLOCK_{len(code_blocks)}__"
        code_blocks[key] = f'<pre><code>{match.group(1)}</code></pre>'
        return key
    text = re.sub(r'```(.*?)```', save_code_block, text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    # 3. Images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', text)

    # 4. Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # 5. Headers
    for i in range(6, 0, -1):
        text = re.sub(r'^' + '#' * i + r'\s+(.*$)', r'<h' + str(i) + r'>\1</h' + str(i) + r'>', text, flags=re.MULTILINE)

    # 6. Blockquotes
    def blockquote_replacer(match):
        content = match.group(0).replace('>', '').strip()
        return f'\n\n<blockquote>{content}</blockquote>\n\n'
    text = re.sub(r'(?:^> .*(?:\n|$))+', blockquote_replacer, text, flags=re.MULTILINE)

    # 7. Lists (Unordered)
    def ul_replacer(match):
        items = match.group(0).strip().split('\n')
        list_items = []
        for item in items:
            item_text = re.sub(r"^[-\*]\s+", "", item).strip()
            list_items.append(f'<li>{item_text}</li>')
        return '\n\n<ul>' + ''.join(list_items) + '</ul>\n\n'
    text = re.sub(r'(?:^[-*] .*(?:\n|$))+', ul_replacer, text, flags=re.MULTILINE)

    # 8. Lists (Ordered)
    def ol_replacer(match):
        items = match.group(0).strip().split('\n')
        list_items = []
        for item in items:
            item_text = re.sub(r"^\d+\.\s+", "", item).strip()
            list_items.append(f'<li>{item_text}</li>')
        return '\n\n<ol>' + ''.join(list_items) + '</ol>\n\n'
    text = re.sub(r'(?:^\d+\. .*(?:\n|$))+', ol_replacer, text, flags=re.MULTILINE)

    # 9. Bold / Italic
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

    # 10. Paragraphs
    # Split by double newline.
    # If a block is not wrapped in a block tag, wrap it in <p>.
    block_tags = ['<h', '<ul', '<ol', '<pre', '<block', '<li', '<img']

    lines = text.split('\n\n')
    new_lines = []
    for line in lines:
        line = line.strip()
        if not line: continue

        # Check if line starts with a known block tag
        is_block = False
        for tag in block_tags:
            if line.startswith(tag):
                is_block = True
                break

        # Also check if it is a placeholder for code block
        if line.startswith('__CODEBLOCK_'):
            is_block = True

        if is_block:
            new_lines.append(line)
        else:
            # Handle single newlines within a paragraph as breaks or spaces?
            # Markdown treats single newlines as spaces.
            line_content = line.replace('\n', ' ')
            new_lines.append(f'<p>{line_content}</p>')

    text = '\n'.join(new_lines)

    # Restore Code Blocks
    for key, value in code_blocks.items():
        text = text.replace(key, value)

    return text

def parse_frontmatter(content):
    """
    Parses YAML-like frontmatter.
    """
    meta = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2]
            for line in frontmatter.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip()] = value.strip()
    return meta, body.strip()

def build():
    start_time = time.time()

    # Check if directories exist
    if not os.path.exists(POSTS_DIR):
        print(f"Error: {POSTS_DIR} directory not found.")
        return
    if not os.path.exists(TEMPLATES_DIR):
        print(f"Error: {TEMPLATES_DIR} directory not found.")
        return

    # Clean and create DIST_DIR
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR)

    # Read Layout
    try:
        with open(os.path.join(TEMPLATES_DIR, 'layout.html'), 'r') as f:
            layout_template = Template(f.read())
    except FileNotFoundError:
        print("Error: layout.html not found in templates/.")
        return

    posts = []

    print(f"Building site from {POSTS_DIR}...")

    # Process Posts
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(POSTS_DIR, filename)
            with open(filepath, 'r') as f:
                content = f.read()

            meta, body_md = parse_frontmatter(content)
            body_html = parse_markdown(body_md)

            # Post Metadata
            title = meta.get('title', 'Untitled')
            date_str = meta.get('date', datetime.now().strftime('%Y-%m-%d'))
            category = meta.get('category', 'Uncategorized')

            # Output filename
            slug = filename.replace('.md', '.html')

            posts.append({
                'title': title,
                'date': date_str,
                'category': category,
                'slug': slug,
                'content': body_html
            })

            # Context for template
            context = {
                'title': title,
                'site_title': SITE_TITLE,
                'author_name': AUTHOR_NAME,
                'year': datetime.now().year,
                'content': f'<article>\n<header class="post-header"><h1>{title}</h1>\n<div class="post-meta">{date_str} | {category}</div></header>\n{body_html}\n</article>',
            }

            # Safe substitute to handle potential missing keys if I forget one,
            # though strict `substitute` is better for debugging.
            try:
                post_html = layout_template.substitute(context)
            except KeyError as e:
                print(f"Error in template substitution for {filename}: Missing key {e}")
                continue

            with open(os.path.join(DIST_DIR, slug), 'w') as f:
                f.write(post_html)

    # Generate Index
    posts.sort(key=lambda x: x['date'], reverse=True)

    index_list_items = []
    for post in posts:
        item = f'<li><span>{post["date"]}</span> <div style="flex-grow:1"><a href="{post["slug"]}">{post["title"]}</a></div> <span class="category">[{post["category"]}]</span></li>'
        index_list_items.append(item)

    index_content = '<ul class="post-list">\n' + '\n'.join(index_list_items) + '\n</ul>'

    index_context = {
        'title': "Home",
        'site_title': SITE_TITLE,
        'author_name': AUTHOR_NAME,
        'year': datetime.now().year,
        'content': index_content
    }

    index_html = layout_template.substitute(index_context)

    with open(os.path.join(DIST_DIR, 'index.html'), 'w') as f:
        f.write(index_html)

    end_time = time.time()
    duration = end_time - start_time
    print(f"Build complete! Generated {len(posts)} posts in {duration:.4f} seconds.")

if __name__ == "__main__":
    build()
