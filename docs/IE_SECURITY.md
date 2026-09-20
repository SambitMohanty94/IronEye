# Security Policy & Hardening Guidelines — IronEye

## 1. Authentication & Access Control
- All API and WebSocket interactions require valid JWT bearer tokens verified via Supabase Auth.
- Role-based permissions are strictly enforced:
  - Only `Admin` role can invoke `POST /api/set_zone` and `POST /api/switch_source`.
  - `Operator` role has write access restricted to incident status updates (`OPEN` -> `RESOLVED`).
  - `Auditor` role is restricted to read-only endpoints.

## 2. Network & Stream Hardening
- Camera streams must use secure RTSPS or authenticated HTTP endpoints.
- Default camera access credentials must never be committed to source control.
- In production, restrict CORS from wildcard `*` to explicitly authorized company domains and origins.

## 3. Database & Row Level Security (RLS)
PostgreSQL RLS must be activated on all tables:
```sql
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE workers ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users with Operator role to update status
CREATE POLICY "Allow operators to update incident status"
ON incidents FOR UPDATE
USING (auth.jwt() ->> 'role' IN ('operator', 'admin'))
WITH CHECK (auth.jwt() ->> 'role' IN ('operator', 'admin'));