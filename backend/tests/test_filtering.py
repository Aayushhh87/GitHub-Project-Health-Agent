from app.utils import filtering


def test_relevant_path_filters_directories_and_binary_files() -> None:
    assert not filtering.is_relevant_path("node_modules/pkg/index.js")
    assert not filtering.is_relevant_path(".git/config")
    assert not filtering.is_relevant_path("assets/logo.png")
    assert not filtering.is_relevant_path("build/app.js")


def test_source_and_priority_files_are_accepted() -> None:
    assert filtering.should_include_file("src/main.py")
    assert filtering.should_include_file("README.md")
    assert filtering.should_include_file("package.json")
    assert filtering.should_include_file("pnpm-lock.yaml")
    assert filtering.file_priority("README.md") < filtering.file_priority("src/main.py")


def test_file_size_filter() -> None:
    assert filtering.should_include_file("src/main.py", filtering.MAX_FILE_SIZE)
    assert not filtering.should_include_file(
        "src/main.py",
        filtering.MAX_FILE_SIZE + 1,
    )