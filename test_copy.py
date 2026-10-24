#!/usr/bin/env python3
"""Test COPY with main cursor."""
import io
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://nexus_admin:nexus_local_dev@127.0.0.1:5433/nexus_fpo')
cur = conn.cursor()

# Clear test table
cur.execute("TRUNCATE TABLE fpos RESTART IDENTITY CASCADE")
conn.commit()

# Test COPY with main cursor - use proper UUID format
buffer = io.StringIO()
buffer.write(f"{uuid.uuid4()}\tTEST-001\tTest FPO\tTest\tTest\t19.0\t73.0\t2020-01-01\ttrue\n")
buffer.write(f"{uuid.uuid4()}\tTEST-002\tTest FPO 2\tTest\tTest\t19.1\t73.1\t2020-01-02\ttrue\n")
buffer.seek(0)

sql = "COPY fpos (fpo_id, fpo_code, fpo_name, district, state, latitude, longitude, registration_date, active_status) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')"
cur.copy_expert(sql, buffer)
conn.commit()
print('COPY works!')

cur.execute('SELECT COUNT(*) FROM fpos')
print('Count:', cur.fetchone())

# Clean up
cur.execute("TRUNCATE TABLE fpos RESTART IDENTITY CASCADE")
conn.commit()
conn.close()
print('Test passed!')