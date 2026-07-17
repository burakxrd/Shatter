# Contributing to Shatter

Thank you for your interest in contributing to Shatter! Here are some guidelines to help you get started.

## 🚀 Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Shatter.git
   cd Shatter
   ```
3. **Install** dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a **branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Development Guidelines

### Code Style
- Follow **PEP 8** for Python code
- Use **type hints** (Python 3.10+ syntax: `X | None` instead of `Optional[X]`)
- Write **docstrings** for all public functions and classes
- Keep functions focused — if a function does too much, split it

### Architecture
- **`core/`** — Backend logic (no UI dependencies)
- **`ui/`** — Frontend bridge and web assets
- **`tests/`** — pytest test suite

### Commit Messages
Use clear, descriptive commit messages:
```
feat: add drag-and-drop support for hash files
fix: handle edge case in NetNTLMv2 detection
docs: update README with new screenshots
test: add unit tests for cap_parser
```

## 🧪 Running Tests

```bash
pytest tests/ -v
```

## 🐛 Reporting Bugs

Please use the [Bug Report](https://github.com/burakxrd/Shatter/issues/new?template=bug_report.md) template when filing bugs. Include:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Hashcat version (if relevant)

## 💡 Feature Requests

Use the [Feature Request](https://github.com/burakxrd/Shatter/issues/new?template=feature_request.md) template. Describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## 📄 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
