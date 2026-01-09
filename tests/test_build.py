import unittest
import os
import shutil
import tempfile
from unittest.mock import patch
import build as build_module

class TestBuild(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.posts_dir = os.path.join(self.test_dir, 'posts')
        self.templates_dir = os.path.join(self.test_dir, 'templates')
        self.dist_dir = os.path.join(self.test_dir, 'dist')

        os.makedirs(self.posts_dir)
        os.makedirs(self.templates_dir)
        # dist_dir is created by build()

        # Create a dummy layout template
        with open(os.path.join(self.templates_dir, 'layout.html'), 'w') as f:
            f.write("<html><body>${content}</body></html>")

        # Patch the configuration in build module
        self.patcher1 = patch('build.POSTS_DIR', self.posts_dir)
        self.patcher2 = patch('build.TEMPLATES_DIR', self.templates_dir)
        self.patcher3 = patch('build.DIST_DIR', self.dist_dir)

        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        shutil.rmtree(self.test_dir)

    def test_parse_frontmatter(self):
        content = """---
title: Test Post
date: 2023-01-01
type: book
tags: [a, b]
---
Content body."""
        meta, body = build_module.parse_frontmatter(content)
        self.assertEqual(meta['title'], 'Test Post')
        self.assertEqual(meta['date'], '2023-01-01')
        self.assertEqual(meta['type'], 'book')
        self.assertEqual(meta['tags'], '[a, b]')
        self.assertEqual(body, 'Content body.')

    def test_parse_markdown(self):
        md = "# Header\n\n**Bold**"
        html = build_module.parse_markdown(md)
        self.assertIn('<h1>Header</h1>', html)
        self.assertIn('<strong>Bold</strong>', html)

    def test_build_separation(self):
        # Create a blog post
        with open(os.path.join(self.posts_dir, 'test_blog.md'), 'w') as f:
            f.write("""---
title: Blog Post
date: 2023-01-01
type: blog
---
Blog content.""")

        # Create a book post
        with open(os.path.join(self.posts_dir, 'test_book.md'), 'w') as f:
            f.write("""---
title: Book Review
date: 2023-01-02
type: book
book_author: Author Name
---
Book content.""")

        # Run build
        build_module.build()

        # Check if index.html contains blog post but NOT book post
        with open(os.path.join(self.dist_dir, 'index.html'), 'r') as f:
            index_content = f.read()
            self.assertIn('Blog Post', index_content)
            self.assertNotIn('Book Review', index_content)

        # Check if books.html contains book post but NOT blog post
        with open(os.path.join(self.dist_dir, 'books.html'), 'r') as f:
            books_content = f.read()
            self.assertIn('Book Review', books_content)
            self.assertIn('Author Name', books_content)
            self.assertNotIn('Blog Post', books_content)

if __name__ == '__main__':
    unittest.main()
