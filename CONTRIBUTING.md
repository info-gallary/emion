# Contributing to EmION

Thank you for your interest in contributing! EmION is an open-source ION-DTN research framework, and we welcome contributions from the DTN community.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/emion.git
   cd emion
   ```
3. **Install** in development mode:
   ```bash
   pip install -e ".[dashboard]"
   ```
4. **Verify** your setup:
   ```bash
   python tests/test_emion.py
   ```

## Making Changes

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test your changes
4. Commit with a clear message: `git commit -m "feat: add CGR route visualization"`
5. Push to your fork: `git push origin feature/your-feature`
6. Open a **Pull Request**

## Code Style

- Python: Follow PEP 8
- JavaScript: Use `const`/`let`, no `var`
- CSS: Use CSS custom properties (variables) from `style.css`

## Types of Contributions

- **Bug Fixes** — Fix issues with ION integration, dashboard UI, or scenario parsing
- **New Modules** — Build anomaly detectors, security modules, or traffic analyzers (see `examples/anomaly_detector/`)
- **Scenarios** — Add new CORE XML scenarios to `examples/`
- **Documentation** — Improve README, coding guide, or add tutorials
- **Tests** — Expand the test suite

## Reporting Issues

Use the GitHub issue tracker. Include:
- Your OS and Python version
- Steps to reproduce
- Expected vs. actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
