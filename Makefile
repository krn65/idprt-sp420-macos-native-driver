.PHONY: all build test test-sanitize package clean

all: build

build:
	./scripts/build.sh

test:
	python3 tests/test_driver.py

test-sanitize:
	python3 tests/test_driver.py --sanitize

package:
	./scripts/build-package.sh

clean:
	python3 -c 'from pathlib import Path; import shutil; [shutil.rmtree(p) for p in (Path("build"), Path("dist")) if p.is_dir() and not p.is_symlink()]'
