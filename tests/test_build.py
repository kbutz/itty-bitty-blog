import unittest
import os
import shutil
from datetime import datetime
from build import parse_frontmatter, parse_markdown, build, POSTS_DIR, DIST_DIR, TEMPLATES_DIR

class TestBuild(unittest.TestCase):

    def setUp(self):
        # Create dummy directories for testing
        if not os.path.exists(POSTS_DIR):
            os.makedirs(POSTS_DIR)
        if not os.path.exists(DIST_DIR):
            os.makedirs(DIST_DIR)
        if not os.path.exists(TEMPLATES_DIR):
            os.makedirs(TEMPLATES_DIR)

        # Create a dummy layout template
        with open(os.path.join(TEMPLATES_DIR, 'layout.html'), 'w') as f:
            f.write("<html><body>${content}</body></html>")

    def tearDown(self):
        # Clean up created files and directories if needed
        # For safety in this environment, I might not want to delete everything
        # if it overlaps with real files, but since we are running in the repo root
        # and using the actual directories, we should be careful.
        # However, the instructions imply using the actual code.
        # I will clean up the specific test files I create.
        pass

    def test_parse_frontmatter(self):
        content = """---
title: Test Post
date: 2023-01-01
type: book
tags: [a, b]
---
Content body."""
        meta, body = parse_frontmatter(content)
        self.assertEqual(meta['title'], 'Test Post')
        self.assertEqual(meta['date'], '2023-01-01')
        self.assertEqual(meta['type'], 'book')
        self.assertEqual(meta['tags'], '[a, b]')
        self.assertEqual(body, 'Content body.')

    def test_parse_markdown(self):
        md = "# Header\n\n**Bold**"
        html = parse_markdown(md)
        self.assertIn('<h1>Header</h1>', html)
        self.assertIn('<strong>Bold</strong>', html)

    def test_build_separation(self):
        # Create a blog post
        with open(os.path.join(POSTS_DIR, 'test_blog.md'), 'w') as f:
            f.write("""---
title: Blog Post
date: 2023-01-01
type: blog
---
Blog content.""")

        # Create a book post
        with open(os.path.join(POSTS_DIR, 'test_book.md'), 'w') as f:
            f.write("""---
title: Book Review
date: 2023-01-02
type: book
book_author: Author Name
---
Book content.""")

        # Run build
        build()

        # Check if index.html contains blog post but NOT book post
        with open(os.path.join(DIST_DIR, 'index.html'), 'r') as f:
            index_content = f.read()
            self.assertIn('Blog Post', index_content)
            self.assertNotIn('Book Review', index_content)

        # Check if books.html contains book post but NOT blog post
        with open(os.path.join(DIST_DIR, 'books.html'), 'r') as f:
            books_content = f.read()
            self.assertIn('Book Review', books_content)
            self.assertIn('Author Name', books_content)
            self.assertNotIn('Blog Post', books_content)

        # Clean up test files
        os.remove(os.path.join(POSTS_DIR, 'test_blog.md'))
        os.remove(os.path.join(POSTS_DIR, 'test_book.md'))

if __name__ == '__main__':
    unittest.main()
