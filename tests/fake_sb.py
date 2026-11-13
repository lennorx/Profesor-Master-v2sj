"""Supabase simulat în memorie (suficient pentru aplicațiile Profesor)."""
import copy, uuid

DB = {"sessions": [], "history": [], "etti_users": [], "etti_tokens": [], "etti_password_resets": [], "etti_api_keys": []}
_hid = [0]


class Resp:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


def _previews():
    out = []
    for s in DB["sessions"]:
        msgs = [h for h in DB["history"] if h["session_id"] == s["session_id"] and h.get("app_id") == s.get("app_id")]
        users = sorted(h["content"] for h in msgs if h["role"] == "user")
        out.append({"session_id": s["session_id"], "app_id": s.get("app_id"), "last_active": s["last_active"],
                    "msg_count": len(msgs), "preview": users[0][:60] if users else None,
                    "etti_user_id": s.get("etti_user_id")})
    return out


class Q:
    def __init__(self, table):
        self.t, self.filters, self.op, self.payload = table, [], "select", None
        self._order, self._limit, self._count, self._ignore = None, None, None, False

    # builders
    def select(self, cols="*", count=None): self.op = "select"; self._count = count; return self
    def insert(self, row): self.op, self.payload = "insert", row; return self
    def upsert(self, row, ignore_duplicates=False): self.op, self.payload, self._ignore = "upsert", row, ignore_duplicates; return self
    def update(self, row): self.op, self.payload = "update", row; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, c, v): self.filters.append(lambda r: r.get(c) == v); return self
    def neq(self, c, v): self.filters.append(lambda r: r.get(c) != v); return self
    def lt(self, c, v): self.filters.append(lambda r: r.get(c) is not None and r.get(c) < v); return self
    def gt(self, c, v): self.filters.append(lambda r: r.get(c) is not None and r.get(c) > v); return self
    def in_(self, c, vs): vs = list(vs); self.filters.append(lambda r: r.get(c) in vs); return self
    def is_(self, c, v): self.filters.append(lambda r: r.get(c) is None); return self
    def order(self, c, desc=False): self._order = (c, desc); return self
    def limit(self, n): self._limit = n; return self

    def _rows(self):
        return _previews() if self.t == "session_previews" else DB[self.t]

    def execute(self):
        rows = self._rows()
        match = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "select":
            if self._order:
                match = sorted(match, key=lambda r: r.get(self._order[0]) or 0, reverse=self._order[1])
            if self._limit is not None:
                match = match[: self._limit]
            return Resp(copy.deepcopy(match), len(match) if self._count else None)
        if self.op in ("insert", "upsert"):
            row = dict(self.payload)
            if self.t == "etti_api_keys":
                row.setdefault("id", str(uuid.uuid4()))
            if self.t == "etti_users":
                row.setdefault("id", str(uuid.uuid4()))
                if any(r["email"] == row["email"] for r in rows):
                    raise Exception("duplicate key value violates unique constraint")
            if self.t == "history":
                if not any(s["session_id"] == row["session_id"] for s in DB["sessions"]):
                    raise Exception("violates foreign key constraint history_session_id_fkey")
                _hid[0] += 1; row["id"] = _hid[0]
            if self.t == "sessions":
                ex = [r for r in rows if r["session_id"] == row["session_id"]]
                if ex:
                    if self.op == "upsert" and self._ignore:
                        return Resp([])
                    if self.op == "upsert":
                        ex[0].update(row); return Resp([ex[0]])
                    raise Exception("duplicate key")
            if self.t == "etti_password_resets" and self.op == "upsert":
                DB[self.t] = [r for r in rows if r["user_id"] != row["user_id"]]; rows = DB[self.t]
            rows.append(row)
            return Resp([copy.deepcopy(row)])
        if self.op == "update":
            for r in match: r.update(self.payload)
            return Resp(copy.deepcopy(match))
        if self.op == "delete":
            DB[self.t] = [r for r in rows if r not in match]
            return Resp(copy.deepcopy(match))


class FakeClient:
    def table(self, name): return Q(name)


def create_client(url, key): return FakeClient()
