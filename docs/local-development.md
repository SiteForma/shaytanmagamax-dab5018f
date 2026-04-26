# Local Development

1. Copy `.env.example` to `.env`.
2. Create a virtual environment and install dependencies:

```bash
make install
```

3. Start infrastructure:

```bash
make compose-up
```

4. Run migrations and seed data:

```bash
make migrate
make seed
```

5. Start services:

```bash
make api
make web
```

Optional worker:

```bash
make worker
```
