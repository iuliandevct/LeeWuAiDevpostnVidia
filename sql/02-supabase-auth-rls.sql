-- ==============================================================================
-- LEEWU AI MARITIME HARNESS — SUPABASE AUTH & ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
-- Architecture: Post-Discharge Cargo Inspection & Autonomous Statutory Verification
-- Database: PostgreSQL 15+ / Supabase Engine
-- Security Baseline: Zero Trust, Role-Based Access Control (RBAC), Row-Level Security (RLS)
-- ==============================================================================

-- 1. EXTENSIONS & SCHEMA SETUP
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. ENUMS & APPLICATION ROLES
DO $$ BEGIN
    CREATE TYPE app_role AS ENUM ('admin', 'surveyor', 'client', 'pi_auditor');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 3. USER PROFILES TABLE (Extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role app_role NOT NULL DEFAULT 'surveyor',
    company TEXT DEFAULT 'LeeWu Maritime Survey',
    license_number TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. SURVEYS MASTER TABLE
CREATE TABLE IF NOT EXISTS public.surveys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ref_no TEXT NOT NULL UNIQUE,
    vessel_name TEXT NOT NULL,
    imo_number TEXT NOT NULL,
    survey_type TEXT NOT NULL DEFAULT 'DISCHARGING SURVEY',
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS', -- 'DRAFT', 'IN_PROGRESS', 'AWAITING_REVIEW', 'APPROVED', 'FINAL'
    port TEXT NOT NULL DEFAULT 'PORT OF CONSTANTA SUD',
    berth TEXT DEFAULT 'Berth 120',
    terminal TEXT DEFAULT 'SCS Terminal',
    date_from DATE,
    date_to DATE,
    assigned_surveyor_id UUID REFERENCES public.profiles(id),
    client_id UUID REFERENCES public.profiles(id),
    client_name TEXT,
    cargo_description TEXT,
    total_packages INT DEFAULT 0,
    total_weight_kg NUMERIC DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. SURVEY EVIDENCE TABLE (Drone Frames, Inspection Photos, Defect Triages)
CREATE TABLE IF NOT EXISTS public.survey_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES public.surveys(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    thumbnail_url TEXT,
    file_type TEXT NOT NULL DEFAULT 'IMAGE', -- 'IMAGE', 'DRONE_VIDEO', 'SCAN'
    hold_location TEXT, -- 'HOLD_1_LH', 'HOLD_5_LH', 'WEATHER_DECK'
    defect_classification TEXT, -- 'SURFACE_RUST', 'CHLORIDE_PITTING', 'MECHANICAL_DENT', 'COMPLIANT'
    confidence_score NUMERIC DEFAULT 0.95,
    surveyor_remarks TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. SURVEY REPORTS TABLE (Statutory A4 Reports & Cryptographic Certifications)
CREATE TABLE IF NOT EXISTS public.survey_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES public.surveys(id) ON DELETE CASCADE,
    report_ref TEXT NOT NULL,
    version INT DEFAULT 1,
    is_final BOOLEAN DEFAULT FALSE,
    signed_by UUID REFERENCES public.profiles(id),
    signed_at TIMESTAMPTZ,
    html_url TEXT,
    pdf_url TEXT,
    cryptographic_sha256 TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. AUDIT LOGS TABLE (Tamper-Proof Audit Trail for P&I Clubs and Courts)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id),
    action TEXT NOT NULL, -- 'LOGIN', 'SIGN_REPORT', 'UPLOAD_EVIDENCE', 'VERIFY_DEFECT'
    resource_type TEXT NOT NULL,
    resource_id UUID,
    ip_address TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- AUTOMATED USER CREATION TRIGGER (auth.users -> public.profiles)
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, role, company, license_number)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        COALESCE((NEW.raw_user_meta_data->>'role')::app_role, 'surveyor'::app_role),
        COALESCE(NEW.raw_user_meta_data->>'company', 'LeeWu Maritime Survey'),
        NEW.raw_user_meta_data->>'license_number'
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        company = EXCLUDED.company,
        role = EXCLUDED.role,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- HELPER FUNCTIONS FOR SECURITY & ROLES
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.get_current_role()
RETURNS app_role AS $$
    SELECT role FROM public.profiles WHERE id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin');
$$ LANGUAGE sql STABLE SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.is_surveyor()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role IN ('surveyor', 'admin'));
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.surveys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.survey_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.survey_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- 1. PROFILES POLICIES
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Authenticated users can view profiles" ON public.profiles;
CREATE POLICY "Authenticated users can view profiles"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (
        id = auth.uid() AND 
        (role = (SELECT role FROM public.profiles WHERE id = auth.uid()) OR public.is_admin())
    );

DROP POLICY IF EXISTS "Admins full manage profiles" ON public.profiles;
CREATE POLICY "Admins full manage profiles"
    ON public.profiles FOR ALL
    TO authenticated
    USING (public.is_admin());

-- ------------------------------------------------------------------------------
-- 2. SURVEYS POLICIES
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Admins have full access to surveys" ON public.surveys;
CREATE POLICY "Admins have full access to surveys"
    ON public.surveys FOR ALL
    TO authenticated
    USING (public.is_admin());

DROP POLICY IF EXISTS "Surveyors can view all surveys" ON public.surveys;
CREATE POLICY "Surveyors can view all surveys"
    ON public.surveys FOR SELECT
    TO authenticated
    USING (public.is_surveyor());

DROP POLICY IF EXISTS "Surveyors can create surveys" ON public.surveys;
CREATE POLICY "Surveyors can create surveys"
    ON public.surveys FOR INSERT
    TO authenticated
    WITH CHECK (public.is_surveyor());

DROP POLICY IF EXISTS "Surveyors can update assigned surveys" ON public.surveys;
CREATE POLICY "Surveyors can update assigned surveys"
    ON public.surveys FOR UPDATE
    TO authenticated
    USING (assigned_surveyor_id = auth.uid() OR public.is_admin())
    WITH CHECK (assigned_surveyor_id = auth.uid() OR public.is_admin());

DROP POLICY IF EXISTS "Clients can view their own surveys" ON public.surveys;
CREATE POLICY "Clients can view their own surveys"
    ON public.surveys FOR SELECT
    TO authenticated
    USING (
        client_id = auth.uid() OR
        client_name = (SELECT company FROM public.profiles WHERE id = auth.uid())
    );

DROP POLICY IF EXISTS "PI Auditors can view surveys" ON public.surveys;
CREATE POLICY "PI Auditors can view surveys"
    ON public.surveys FOR SELECT
    TO authenticated
    USING (public.get_current_role() = 'pi_auditor');

-- ------------------------------------------------------------------------------
-- 3. SURVEY EVIDENCE POLICIES
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Surveyors can manage evidence" ON public.survey_evidence;
CREATE POLICY "Surveyors can manage evidence"
    ON public.survey_evidence FOR ALL
    TO authenticated
    USING (public.is_surveyor());

DROP POLICY IF EXISTS "Clients and Auditors can view survey evidence" ON public.survey_evidence;
CREATE POLICY "Clients and Auditors can view survey evidence"
    ON public.survey_evidence FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.surveys s
            WHERE s.id = survey_evidence.survey_id AND (
                s.client_id = auth.uid() OR
                s.client_name = (SELECT company FROM public.profiles WHERE id = auth.uid()) OR
                public.get_current_role() = 'pi_auditor' OR
                public.is_surveyor()
            )
        )
    );

-- ------------------------------------------------------------------------------
-- 4. SURVEY REPORTS POLICIES
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Surveyors can create and edit reports" ON public.survey_reports;
CREATE POLICY "Surveyors can create and edit reports"
    ON public.survey_reports FOR ALL
    TO authenticated
    USING (public.is_surveyor());

DROP POLICY IF EXISTS "Clients can view final reports only" ON public.survey_reports;
CREATE POLICY "Clients can view final reports only"
    ON public.survey_reports FOR SELECT
    TO authenticated
    USING (
        is_final = TRUE AND EXISTS (
            SELECT 1 FROM public.surveys s
            WHERE s.id = survey_reports.survey_id AND (
                s.client_id = auth.uid() OR
                s.client_name = (SELECT company FROM public.profiles WHERE id = auth.uid())
            )
        )
    );

DROP POLICY IF EXISTS "Auditors can review all reports" ON public.survey_reports;
CREATE POLICY "Auditors can review all reports"
    ON public.survey_reports FOR SELECT
    TO authenticated
    USING (public.get_current_role() = 'pi_auditor');

-- ------------------------------------------------------------------------------
-- 5. AUDIT LOGS POLICIES
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Authenticated users can append audit logs" ON public.audit_logs;
CREATE POLICY "Authenticated users can append audit logs"
    ON public.audit_logs FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Admins and Auditors can view audit logs" ON public.audit_logs;
CREATE POLICY "Admins and Auditors can view audit logs"
    ON public.audit_logs FOR SELECT
    TO authenticated
    USING (public.is_admin() OR public.get_current_role() = 'pi_auditor');

-- ==============================================================================
-- SEED DATA: MARITIME USERS, PROFILES & SURVEYS
-- ==============================================================================

DO $$
DECLARE
    admin_id UUID := 'a0000000-0000-0000-0000-000000000001';
    surveyor_id UUID := 'a0000000-0000-0000-0000-000000000002';
    client_id UUID := 'a0000000-0000-0000-0000-000000000003';
    auditor_id UUID := 'a0000000-0000-0000-0000-000000000004';
    hashed_pw TEXT := crypt('demo-session-auth', gen_salt('bf'));
    srv_wanfu_id UUID := 'b0000000-0000-0000-0000-000000000001';
    srv_atlantic_id UUID := 'b0000000-0000-0000-0000-000000000002';
BEGIN
    -- 1. Insert into auth.users (Supabase Engine)
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth') THEN
        -- Admin: Captain Radu Ionescu
        INSERT INTO auth.users (
            id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
            raw_app_meta_data, raw_user_meta_data, created_at, updated_at
        ) VALUES (
            admin_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
            'admin@leewu.maritime.ai', hashed_pw, NOW(),
            '{"provider":"email","providers":["email"]}'::jsonb,
            '{"full_name":"Captain Radu Ionescu","role":"admin","company":"LeeWu Maritime AI HQ"}'::jsonb,
            NOW(), NOW()
        ) ON CONFLICT (id) DO UPDATE SET encrypted_password = EXCLUDED.encrypted_password;

        -- Surveyor: Ing. Alexandru Radu
        INSERT INTO auth.users (
            id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
            raw_app_meta_data, raw_user_meta_data, created_at, updated_at
        ) VALUES (
            surveyor_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
            'alexandru.radu@leewuai.ro', hashed_pw, NOW(),
            '{"provider":"email","providers":["email"]}'::jsonb,
            '{"full_name":"Ing. Alexandru Radu","role":"surveyor","company":"LeeWu Maritime Survey","license_number":"DEMO-MWS-2026-001"}'::jsonb,
            NOW(), NOW()
        ) ON CONFLICT (id) DO UPDATE SET encrypted_password = EXCLUDED.encrypted_password;

        -- Client: Elena Dobre (COSCO)
        INSERT INTO auth.users (
            id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
            raw_app_meta_data, raw_user_meta_data, created_at, updated_at
        ) VALUES (
            client_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
            'client@globalocean.example', hashed_pw, NOW(),
            '{"provider":"email","providers":["email"]}'::jsonb,
            '{"full_name":"Elena Dobre","role":"client","company":"GLOBAL OCEAN SHIPPING & TRADING S.R.L."}'::jsonb,
            NOW(), NOW()
        ) ON CONFLICT (id) DO UPDATE SET encrypted_password = EXCLUDED.encrypted_password;

        -- P&I Auditor: Henrik Lindqvist (Gard)
        INSERT INTO auth.users (
            id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
            raw_app_meta_data, raw_user_meta_data, created_at, updated_at
        ) VALUES (
            auditor_id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
            'auditor@gard-pi.com', hashed_pw, NOW(),
            '{"provider":"email","providers":["email"]}'::jsonb,
            '{"full_name":"Henrik Lindqvist","role":"pi_auditor","company":"Gard P&I Club Norway"}'::jsonb,
            NOW(), NOW()
        ) ON CONFLICT (id) DO UPDATE SET encrypted_password = EXCLUDED.encrypted_password;
    END IF;

    -- 2. Upsert Public Profiles
    INSERT INTO public.profiles (id, email, full_name, role, company, license_number)
    VALUES 
        (admin_id, 'admin@leewu.maritime.ai', 'Captain Radu Ionescu', 'admin', 'LeeWu Maritime AI HQ', 'HQ-ADM-001'),
        (surveyor_id, 'alexandru.radu@leewuai.ro', 'Ing. Alexandru Radu', 'surveyor', 'LeeWu Maritime Survey', 'DEMO-MWS-2026-001'),
        (client_id, 'client@globalocean.example', 'Elena Dobre', 'client', 'GLOBAL OCEAN SHIPPING & TRADING S.R.L.', NULL),
        (auditor_id, 'auditor@gard-pi.com', 'Henrik Lindqvist', 'pi_auditor', 'Gard P&I Club Norway', 'GARD-AUD-2024-EU')
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        role = EXCLUDED.role,
        company = EXCLUDED.company,
        license_number = EXCLUDED.license_number,
        updated_at = NOW();

    -- 3. Upsert Sample Surveys with Direct Role Ownership
    INSERT INTO public.surveys (
        id, ref_no, vessel_name, imo_number, survey_type, status, port, berth, terminal,
        date_from, date_to, assigned_surveyor_id, client_id, client_name, cargo_description,
        total_packages, total_weight_kg
    ) VALUES 
        (
            srv_wanfu_id, 'SRV062_2026', 'WAN FU', '1072842', 'DISCHARGING SURVEY', 'FINAL',
            'PORT OF CONSTANTA SUD', 'Berth 120', 'SCS Terminal',
            '2026-06-22', '2026-06-24', surveyor_id, client_id,
            'GLOBAL OCEAN SHIPPING & TRADING S.R.L.',
            'I-Beam and Steel Items (WF03ZJGCON28Z)', 3, 11020
        ),
        (
            srv_atlantic_id, 'SRV-2025-0891', 'MV Atlantic Pioneer', '9482718', 'ONBOARD STAGE 3', 'IN_PROGRESS',
            'PORT OF CONSTANTA SUD', 'Berth 120', 'SCS Terminal',
            '2026-10-28', '2026-10-30', surveyor_id, NULL,
            'CARGILL GRAIN LOGISTICS',
            'Bulk Grain & Steel Coils', 450, 2850000
        )
    ON CONFLICT (ref_no) DO UPDATE SET
        assigned_surveyor_id = EXCLUDED.assigned_surveyor_id,
        client_id = EXCLUDED.client_id,
        status = EXCLUDED.status;

    -- 4. Sample Survey Report with Cryptographic Integrity Hash
    INSERT INTO public.survey_reports (
        survey_id, report_ref, version, is_final, signed_by, signed_at,
        html_url, pdf_url, cryptographic_sha256
    ) VALUES (
        srv_wanfu_id, 'SRV062_2026_FINAL', 1, TRUE, surveyor_id, NOW(),
        'survey.html', 'Discharge_Cargo_Survey_WAN_FU_PL062.pdf',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    ) ON CONFLICT DO NOTHING;

    -- 5. Audit Log Entry
    INSERT INTO public.audit_logs (user_id, action, resource_type, resource_id, details)
    VALUES (
        surveyor_id, 'SIGN_REPORT', 'survey_reports', srv_wanfu_id,
        '{"vessel":"WAN FU","ref_no":"SRV062_2026","action":"Signed and sealed by Ing. Alexandru Radu"}'::jsonb
    ) ON CONFLICT DO NOTHING;

END $$;

-- Grant Schema Permissions to Authenticated and Anon Roles

-- ==============================================================================
-- 8. PGVECTOR & RAG EMBEDDINGS SCHEMA (Honcho & Semantic Search Engine)
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS "vector";

-- Document Embeddings Table
CREATE TABLE IF NOT EXISTS public.document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL,
    document_type TEXT NOT NULL, -- 'SURVEY_REPORT', 'STATUTORY_LAW', 'CARGO_MANIFEST', 'CASE_LAW', 'HONCHO_MEMORY'
    chunk_index INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536), -- Standard embedding dimension (OpenAI, NeMo NV-Embed-QA, Gemini)
    client_id UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW Vector Index for High-Throughput Approximate Nearest Neighbors (ANN)
CREATE INDEX IF NOT EXISTS doc_embeddings_hnsw_idx 
    ON public.document_embeddings 
    USING hnsw (embedding vector_cosine_ops);

-- Enable RLS on Embeddings
ALTER TABLE public.document_embeddings ENABLE ROW LEVEL SECURITY;

-- Embeddings RLS Policies
DROP POLICY IF EXISTS "Surveyors and Admins can view all embeddings" ON public.document_embeddings;
CREATE POLICY "Surveyors and Admins can view all embeddings"
    ON public.document_embeddings FOR SELECT
    TO authenticated
    USING (public.is_surveyor() OR public.get_current_role() = 'pi_auditor');

DROP POLICY IF EXISTS "Clients can view their own and public statutory embeddings" ON public.document_embeddings;
CREATE POLICY "Clients can view their own and public statutory embeddings"
    ON public.document_embeddings FOR SELECT
    TO authenticated
    USING (
        document_type IN ('STATUTORY_LAW', 'PUBLIC_PRECEDENT') OR
        client_id = auth.uid() OR
        (metadata->>'client_name') = (SELECT company FROM public.profiles WHERE id = auth.uid())
    );

DROP POLICY IF EXISTS "Surveyors and Admins can insert embeddings" ON public.document_embeddings;
CREATE POLICY "Surveyors and Admins can insert embeddings"
    ON public.document_embeddings FOR INSERT
    TO authenticated
    WITH CHECK (public.is_surveyor());

-- Semantic Similarity Match Function (RPC for Supabase / PostgreSQL)
CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.70,
    match_count INT DEFAULT 5,
    filter_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    document_id TEXT,
    document_type TEXT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.document_id,
        e.document_type,
        e.content,
        e.metadata,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM public.document_embeddings e
    WHERE 
        (filter_type IS NULL OR e.document_type = filter_type)
        AND 1 - (e.embedding <=> query_embedding) > match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;


-- ==============================================================================
-- 7. FIELD SURVEYOR OPERATIONS, REMARKS, FLEET & ACCOUNTING BRAIN
-- ==============================================================================

-- 7.1 Tabel Remarks Piese Bulite & Avarii (Sincronizat Telegram)
CREATE TABLE IF NOT EXISTS public.survey_damage_remarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID REFERENCES public.surveys(id) ON DELETE CASCADE,
    hold_no INT NOT NULL,
    item_ref TEXT NOT NULL,
    description TEXT NOT NULL,
    photo_timestamp TIMESTAMPTZ NOT NULL,
    severity TEXT NOT NULL DEFAULT 'CRITIC' CHECK (severity IN ('CRITIC', 'MEDIU', 'MINOR')),
    attributed_party TEXT,
    hague_visby_article TEXT DEFAULT 'Art. III r.2 (Custody & Care of Cargo)',
    created_via TEXT DEFAULT 'Telegram Bot (@LpMaritimeSurveyBot)',
    surveyor_name TEXT DEFAULT 'Alexandru Radu',
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW())
);

ALTER TABLE public.survey_damage_remarks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone authenticated can view damage remarks"
    ON public.survey_damage_remarks FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Surveyors and admins can insert damage remarks"
    ON public.survey_damage_remarks FOR INSERT
    TO authenticated
    WITH CHECK (
        public.current_app_role() IN ('admin', 'surveyor')
    );

-- 7.2 Pontaj Automat Surveyor (Reconstruit din EXIF Poze)
CREATE TABLE IF NOT EXISTS public.surveyor_timesheets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID REFERENCES public.surveys(id) ON DELETE CASCADE,
    surveyor_id UUID REFERENCES auth.users(id),
    surveyor_name TEXT NOT NULL DEFAULT 'Alexandru Radu',
    work_date DATE NOT NULL DEFAULT CURRENT_DATE,
    first_photo_time TIMESTAMPTZ NOT NULL,
    last_photo_time TIMESTAMPTZ NOT NULL,
    total_on_site_hours NUMERIC(5,2) NOT NULL,
    weather_stoppage_hours NUMERIC(5,2) DEFAULT 0.00,
    net_billable_hours NUMERIC(5,2) NOT NULL,
    hourly_rate_ron NUMERIC(8,2) DEFAULT 185.00,
    total_amount_ron NUMERIC(10,2) GENERATED ALWAYS AS (net_billable_hours * hourly_rate_ron) STORED,
    accounting_status TEXT DEFAULT 'APPROVED' CHECK (accounting_status IN ('PENDING', 'APPROVED', 'INVOICED')),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW())
);

ALTER TABLE public.surveyor_timesheets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone authenticated can view timesheets"
    ON public.surveyor_timesheets FOR SELECT
    TO authenticated
    USING (true);

-- 7.3 Flotă Auto LeeWu Maritime & Remindere Acte (ITP, RCA, Rovinietă)
CREATE TABLE IF NOT EXISTS public.fleet_vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plate_no TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    assigned_driver TEXT NOT NULL,
    odometer_km INT NOT NULL DEFAULT 0,
    fuel_type TEXT NOT NULL DEFAULT 'Diesel',
    rca_expiry DATE NOT NULL,
    rca_insurer TEXT DEFAULT 'Allianz-Tiriac',
    itp_expiry DATE NOT NULL,
    rovinieta_expiry DATE NOT NULL,
    casco_expiry DATE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW())
);

ALTER TABLE public.fleet_vehicles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view fleet vehicles"
    ON public.fleet_vehicles FOR SELECT
    TO authenticated
    USING (true);

-- 7.4 Foi de Parcurs & Calcul Randament (Cost / Km)
CREATE TABLE IF NOT EXISTS public.fleet_logbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    foaie_serie TEXT UNIQUE NOT NULL,
    vehicle_plate TEXT REFERENCES public.fleet_vehicles(plate_no) ON DELETE RESTRICT,
    driver_name TEXT NOT NULL,
    trip_date DATE NOT NULL DEFAULT CURRENT_DATE,
    route_desc TEXT NOT NULL,
    mission_purpose TEXT NOT NULL,
    km_start INT NOT NULL,
    km_end INT NOT NULL,
    distance_km INT GENERATED ALWAYS AS (km_end - km_start) STORED,
    fuel_liters NUMERIC(6,2) NOT NULL,
    fuel_cost_ron NUMERIC(8,2) NOT NULL,
    maintenance_cost_ron NUMERIC(8,2) NOT NULL,
    total_trip_cost_ron NUMERIC(8,2) NOT NULL,
    cost_per_km_ron NUMERIC(6,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::text, NOW())
);

ALTER TABLE public.fleet_logbooks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view logbooks"
    ON public.fleet_logbooks FOR SELECT
    TO authenticated
    USING (true);

-- Seed Data pentru Flotă & Remindere
INSERT INTO public.fleet_vehicles (plate_no, model, assigned_driver, odometer_km, fuel_type, rca_expiry, itp_expiry, rovinieta_expiry)
VALUES
    ('CT-88-LPM', 'Dacia Duster 4x4 1.5 dCi', 'Alexandru Radu', 142358, 'Diesel', '2026-12-11', '2026-11-17', '2027-02-21'),
    ('CT-22-LPM', 'Renault Megane Estate 1.3 TCe', 'Radu Mihai', 89410, 'Benzina', '2027-01-27', '2027-03-19', '2026-11-06')
ON CONFLICT (plate_no) DO NOTHING;
