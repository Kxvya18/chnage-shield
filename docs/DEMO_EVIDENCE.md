# Demo evidence and runtime notes

## Verified commands

These commands were run successfully against the project:

```bash
cd /Users/boolu/Desktop/simulations/ALL\ PROJECTS/changeshield
source .venv/bin/activate
python manage.py test control.tests.test_services --verbosity 2
```

Observed result:

- exit code: 0
- test suite passed

```bash
curl -I -s http://localhost:8069/web/login | head
```

Observed result:

- HTTP/1.1 303 SEE OTHER
- Odoo login endpoint responded successfully

```bash
source .venv/bin/activate
python manage.py shell -c "from control.models import Run; r=Run.objects.order_by('-id').first(); print(r.status if r else None)"
```

Observed result during live validation:

- status reported as `failed`
- diagnosis record existed for the run
- failure event was captured in Django

## Observed runtime behavior

The live queue-to-worker flow produced a real run that reached a diagnosed failure state in the control plane. This is evidence that the project demonstrates the intended lifecycle:

1. queued run created
2. worker claims run
3. Playwright executes browser flow
4. run fails with captured evidence
5. diagnosis record created
6. policy gate can reject or evaluate the proposal

## Important caveat

This is a prototype, not a fully stabilized production deployment. The Odoo + Docker environment remains sensitive to host-level Docker metadata/network conditions, and the production-hardening path is documented separately in [docs/PRODUCTION_PATH.md](docs/PRODUCTION_PATH.md).
