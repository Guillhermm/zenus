# Testing Guide

**Status**: ✅ Complete | **Phase**: Foundation Hardening

Comprehensive testing infrastructure for Zenus with unit, integration, and E2E tests.

## 📋 Test Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests (test tool interactions)
├── e2e/              # End-to-end tests (complete workflows)
└── fixtures/         # Shared test fixtures
```

## 🚀 Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test Types
```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# Skip slow tests
pytest -m "not slow"

# Run only slow tests
pytest -m "slow"
```

### Run Tests with Coverage
```bash
cd packages/core
poetry run pytest ../../tests/unit -v --cov=zenus_core --cov-report=html
```

View coverage report: `open packages/core/htmlcov/index.html`

## 📦 Test Categories

### Unit Tests (`tests/unit/`)
Fast, isolated tests for individual components:
- `test_file_ops.py` - FileOps tool tests
- `test_schemas.py` - Schema validation tests
- `test_safety_policy.py` - Safety policy tests
- `test_planner.py` - Planner logic tests
- `test_action_tracker.py` - Action tracking tests
- `test_failure_analyzer.py` - Failure analysis tests

**Characteristics:**
- Fast (<10ms per test)
- No external dependencies
- No file system modifications (use temp directories)
- No network calls (use mocks)

### Integration Tests (`tests/integration/`)
Tests that verify tool interactions with the system:
- `test_system_ops.py` - SystemOps integration tests
- `test_git_ops.py` - GitOps integration tests

**Characteristics:**
- Medium speed (<200ms per test)
- Real file system operations (in temp directories)
- Real git operations
- Real system queries (CPU, memory, processes)

### E2E Tests (`tests/e2e/`)
Complete workflow tests from user intent to execution:
- `test_file_workflow.py` - File operation workflows
- `test_system_monitoring_workflow.py` - System monitoring workflows

**Characteristics:**
- Slower (up to 1s per test)
- Complete user workflows
- Multiple tools working together
- Real-world scenarios

## 🛠️ Test Fixtures

Shared fixtures in `tests/fixtures/conftest.py`:

### Directory Fixtures
```python
def test_example(temp_dir):
    # temp_dir is automatically created and cleaned up
    file_path = Path(temp_dir) / "test.txt"
    file_path.write_text("content")
```

### Git Repository Fixture
```python
def test_git_operations(git_repo):
    # git_repo is a temp directory with initialized git repo
    # Has one commit with README.md
```

### Sample Files Fixture
```python
def test_file_operations(sample_files):
    # sample_files is a dict of file paths
    # Contains: doc1.txt, doc2.txt, image1.jpg, data.csv
```

### Project Structure Fixture
```python
def test_project_workflow(sample_project_structure):
    # sample_project_structure is a complete project layout
    # Contains: src/, tests/, docs/, README.md, etc.
```

## 🏷️ Test Markers

Use markers to categorize and filter tests:

```python
@pytest.mark.slow
def test_large_file_processing():
    # Slow tests (>1s)
    pass

@pytest.mark.e2e
def test_complete_workflow():
    # End-to-end tests
    pass

@pytest.mark.integration
def test_tool_integration():
    # Integration tests
    pass

@pytest.mark.requires_git
def test_git_feature():
    # Tests that require git
    pass
```

Run tests by marker:
```bash
pytest -m "slow"                  # Only slow tests
pytest -m "not slow"              # Skip slow tests
pytest -m "e2e and not slow"      # E2E tests, skip slow ones
```

## 🔄 CI/CD Pipeline

Tests run automatically on every push and pull request via GitHub Actions.

### Workflow Triggers
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

### Test Matrix
- **OS**: Ubuntu, macOS
- **Python**: 3.10, 3.11, 3.12

### Stages
1. **Unit Tests** - Fast tests with coverage
2. **Integration Tests** - Tool integration tests
3. **E2E Tests** - Complete workflows (non-slow)
4. **Lint** - Code quality checks (black, isort, mypy)
5. **Slow Tests** - Long-running tests (main branch only)

### Coverage Reports
Coverage reports are uploaded to Codecov automatically.

## ✍️ Writing Tests

### Example Unit Test
```python
class TestFileOps:
    def setup_method(self):
        self.tool = FileOps()
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        shutil.rmtree(self.test_dir)
    
    def test_scan_directory(self):
        # Create test files
        Path(self.test_dir, "file1.txt").touch()
        
        # Execute
        result = self.tool.scan(self.test_dir)
        
        # Assert
        assert "file1.txt" in result
```

### Example Integration Test
```python
class TestSystemOps:
    def setup_method(self):
        self.tool = SystemOps()
    
    def test_check_resource_usage(self):
        result = self.tool.check_resource_usage()
        
        assert "CPU:" in result
        assert "Memory:" in result
        assert "Disk:" in result
```

### Example E2E Test
```python
@pytest.mark.e2e
class TestFileWorkflows:
    def test_organize_files_by_extension(self, temp_dir):
        # Setup: Create files
        for fname in ["doc1.txt", "image1.jpg"]:
            Path(temp_dir, fname).touch()
        
        # Execute: Organize files
        file_ops = FileOps()
        file_ops.mkdir(str(Path(temp_dir, "txt")))
        file_ops.move(str(Path(temp_dir, "*.txt")), 
                     str(Path(temp_dir, "txt")))
        
        # Verify: Files organized
        assert Path(temp_dir, "txt", "doc1.txt").exists()
```

## 🎯 Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Descriptive Names
```python
# Good
def test_scan_directory_returns_file_list():
    pass

# Bad
def test_scan():
    pass
```

### 3. Clear Assertions
```python
# Good
assert result == expected, f"Expected {expected}, got {result}"

# Bad
assert result == expected
```

### 4. Use Fixtures
```python
# Good - Use fixture
def test_with_temp_dir(temp_dir):
    file_path = Path(temp_dir) / "test.txt"

# Bad - Manual setup
def test_without_fixture():
    temp_dir = tempfile.mkdtemp()
    try:
        file_path = Path(temp_dir) / "test.txt"
    finally:
        shutil.rmtree(temp_dir)
```

### 5. Performance Tests
```python
@pytest.mark.slow
def test_performance():
    import time
    start = time.time()
    
    # Test code
    
    elapsed = time.time() - start
    assert elapsed < 1.0, f"Too slow: {elapsed:.2f}s"
```

## 🐛 Debugging Tests

### Run Single Test
```bash
pytest tests/unit/test_file_ops.py::TestFileOps::test_scan_directory -v
```

### Show Print Statements
```bash
pytest -s tests/unit/test_file_ops.py
```

### Drop into Debugger on Failure
```bash
pytest --pdb tests/
```

### Show Local Variables on Failure
```bash
pytest -l tests/
```

## 📊 Test Coverage

### Current Coverage
Target: **>85%**

### View Coverage
```bash
cd packages/core
poetry run pytest ../../tests/ --cov=zenus_core --cov-report=term-missing
```

### Missing Coverage
Focus on these areas:
- Error handling paths
- Edge cases
- Rarely-used features

## 🚀 Continuous Improvement

### Add Tests When:
- **New features**: Add tests before implementation (TDD)
- **Bug fixes**: Add regression tests
- **Refactoring**: Ensure tests still pass

### Review Tests When:
- Tests become flaky
- Tests take too long
- Coverage drops

---

**Next Steps:**
1. Add more integration tests for remaining tools (NetworkOps, ProcessOps, etc.)
2. Add more E2E tests for complex workflows
3. Improve coverage for edge cases
4. Add performance benchmarks
