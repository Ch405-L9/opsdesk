-- Criteria whose answer is sensitive resolve at runtime from private/screening.json.
-- Tracked data stores only the key and the passing value; status stays 'unknown'.
ALTER TABLE criteria ADD COLUMN private_key TEXT;
ALTER TABLE criteria ADD COLUMN pass_when TEXT CHECK (pass_when IS NULL OR pass_when IN ('true','false'));
