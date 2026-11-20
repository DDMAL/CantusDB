from django.db import migrations

# The existing indexes cover compact IDs. Check full record URLs across
# all labels so that changing the spelling of a database cannot claim
# another country's record. Country reads need no join or extra query.
unique_authority_urls = migrations.RunSQL(
    """
    CREATE FUNCTION main_app_check_country_authority_urls() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE
        urls text[];
    BEGIN
        SELECT array_agg(value) INTO urls FROM jsonb_each_text(NEW.authorities)
        WHERE value ~* '^https?://';
        IF urls IS NOT NULL THEN
            -- Country edits are rare. Serialize URL assignments so concurrent
            -- admin or bulk writes cannot both claim the same record.
            PERFORM pg_advisory_xact_lock(TG_RELID::int, 1);
            IF EXISTS (
                SELECT FROM main_app_country
                WHERE id <> NEW.id AND jsonb_path_query_array(authorities, '$.*') ?| urls
            ) THEN
                RAISE unique_violation USING MESSAGE = 'A country already uses this authority record URL.';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$;
    CREATE TRIGGER main_app_country_authority_urls
    BEFORE INSERT OR UPDATE OF authorities ON main_app_country
    FOR EACH ROW WHEN (NEW.authorities <> '{}'::jsonb)
    EXECUTE FUNCTION main_app_check_country_authority_urls();
    """,
    """
    DROP TRIGGER main_app_country_authority_urls ON main_app_country;
    DROP FUNCTION main_app_check_country_authority_urls();
    """,
)
