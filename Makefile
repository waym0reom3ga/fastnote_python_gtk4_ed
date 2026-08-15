.PHONY: all clean test

BIN := fastnote_python_gtk4

all: $(BIN)

$(BIN): src/main.py src/*.py
	nuitka --onefile --output-filename=$(BIN) \
		--include-package=src \
		src/main.py

test: $(BIN)
	./$(BIN) --version

clean:
	rm -rf $(BIN) main.build main.onefile-build main.dist
