PYTHON ?= python3
TOPOLOGY := topology.clab.yml

.PHONY: deploy verify test inspect destroy

deploy:
	sudo containerlab deploy --topo $(TOPOLOGY) --reconfigure

verify:
	$(PYTHON) scripts/verify_lab.py --report evidence/latest-run.json

test:
	$(PYTHON) -m unittest discover -s tests -v

inspect:
	sudo containerlab inspect --topo $(TOPOLOGY)

destroy:
	sudo containerlab destroy --topo $(TOPOLOGY) --cleanup
