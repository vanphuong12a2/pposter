.PHONY: run
run:
	python pposter.py

.PHONY: clean
clean:
	@find ./ -name "*.pyc" -exec rm -f {} \;
	@find ./ -name "*~" -exec rm -f {} \;
	@find ./ -name "__pycache__" -exec rm -f {} \;

.PHONY: test
test: pep8
	py.test  -v -s ./test_pposter.py

.PHONY: pep8
pep8:
	@flake8 .

.PHONY: dependencies
pep8:
	pip install -r config/requirements.txt
