# HELP.md — Implementare n8n RAG pe stație nouă

Acest ghid este pentru mutarea workflow-ului n8n pe alt calculator / server.

Workflow-ul folosește:

- **Google Drive** — detectează fișiere noi într-un folder și le descarcă automat
- **Google Gemini Embeddings** — transformă documentele în vectori
- **Supabase Vector Store** — stochează documentele indexate
- **OpenRouter Chat Model** — modelul AI folosit de agent
- **n8n AI Agent** — răspunde folosind documentele din Supabase

---

## 1. Fișiere necesare

Pune în GitHub:

```text
workflow.json
HELP.md
```

Workflow-ul JSON se importă în n8n din:

```text
n8n → Workflows → Import from file / clipboard
```

---

## 2. Folder Google Drive folosit

Folderul monitorizat este:

```text
https://drive.google.com/drive/folders/1f4FYK5ph7dzDsjgxi3OW5Mhe4PTzNJ3L
```

Folder ID:

```text
1f4FYK5ph7dzDsjgxi3OW5Mhe4PTzNJ3L
```

În node-ul **Google Drive Trigger - New File in Folder**, câmpul folder trebuie să fie acest ID.

---

## 3. Credentiale necesare în n8n

Pe stația nouă trebuie create din nou credentialele. Ele NU se mută automat prin JSON.

Ai nevoie de 4 credentiale:

### 3.1 Google Drive OAuth2

Folosit pentru:

```text
Google Drive Trigger - New File in Folder
Download New Google Drive File
```

Pași:

1. În Google Cloud Console creezi / folosești un OAuth Client.
2. Activezi **Google Drive API**.
3. În n8n creezi credential de tip **Google Drive OAuth2**.
4. Copiezi din n8n câmpul **OAuth Redirect URL**.
5. Îl pui în Google Cloud la:

```text
APIs & Services → Credentials → OAuth 2.0 Client IDs → Authorized redirect URIs
```

6. Revii în n8n și apeși **Connect / Reconnect**.

Dacă apare eroare `invalid_grant`, șterge credentialul și refă-l. Verifică să fie identic redirect URL-ul.

---

### 3.2 Google Gemini API key

Folosit pentru embeddings:

```text
Embeddings Google Gemini
Embeddings Google Gemini2
```

Nu este același credential cu Google Drive.

Ai nevoie de API key din Google AI Studio.

Model recomandat:

```text
models/gemini-embedding-001
```

Dacă n8n nu acceptă cu `models/`, folosește:

```text
gemini-embedding-001
```

Important: același model trebuie pus în ambele node-uri de embeddings.

---

### 3.3 OpenRouter API key

Folosit pentru:

```text
OpenRouter Chat Model
```

Model recomandat pentru început:

```text
openai/gpt-4o-mini
```

Poți folosi și modele Google / Anthropic prin OpenRouter, dar credentialul rămâne OpenRouter.

---

### 3.4 Supabase credential

Folosit pentru:

```text
Supabase Vector Store - Insert
Supabase Vector Store - RAG Tool
```

În n8n configurezi:

```text
Supabase URL: https://xxxxx.supabase.co
Supabase Service Role Key: cheia service_role
```

Folosește **service_role key**, nu `anon key`, pentru inserare documente.

---

## 4. Configurare Supabase

În Supabase → SQL Editor rulează scriptul de mai jos.

Acest setup este pentru **Gemini embedding 001**, care produce vectori de **3072 dimensiuni**.

> Atenție: `drop table if exists documents;` șterge documentele deja indexate. Rulează-l doar pe setup nou sau dacă accepți resetarea bazei.

```sql
create extension if not exists vector;

drop table if exists documents;

create table documents (
  id bigserial primary key,
  content text,
  metadata jsonb,
  embedding vector(3072)
);

create or replace function match_documents (
  query_embedding vector(3072),
  match_count int default 5,
  filter jsonb default '{}'
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from documents d
  where d.metadata @> filter
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

Important: funcția folosește `d.metadata`, nu doar `metadata`, ca să eviți eroarea:

```text
column reference "metadata" is ambiguous
```

---

## 5. Structura corectă a workflow-ului

### 5.1 Partea de indexare automată

```text
Google Drive Trigger - New File in Folder
        ↓
Download New Google Drive File
        ↓
Set File Metadata, opțional
        ↓
Supabase Vector Store - Insert
```

Sub-node-uri obligatorii:

```text
Recursive Character Text Splitter
        ↓
Default Data Loader
        ↓
Supabase Vector Store - Insert
```

și:

```text
Embeddings Google Gemini2
        ↓
Supabase Vector Store - Insert
```

---

### 5.2 Partea de chat / RAG

```text
When chat message received
        ↓
AI Agent
```

Sub-node-uri:

```text
OpenRouter Chat Model
        ↓
AI Agent
```

```text
Supabase Vector Store - RAG Tool
        ↓
AI Agent
```

```text
Embeddings Google Gemini
        ↓
Supabase Vector Store - RAG Tool
```

---

## 6. Setări importante pe node-uri

### 6.1 Google Drive Trigger - New File in Folder

```text
Event: File Created
Folder: Specific Folder
Folder ID: 1f4FYK5ph7dzDsjgxi3OW5Mhe4PTzNJ3L
Poll: Every minute / Every 5 minutes
Credential: Google Drive OAuth2
```

---

### 6.2 Download New Google Drive File

```text
Operation: Download
File ID: {{ $json.id }}
Binary Property: data
Credential: Google Drive OAuth2
```

După rulare trebuie să vezi în output:

```text
Binary → data
```

Dacă nu există `Binary → data`, Default Data Loader nu poate citi fișierul.

---

### 6.3 Set File Metadata, opțional

Dacă folosești acest node, ai grijă să nu șteargă binary-ul.

Setări importante:

```text
Keep Binary Data: ON
Include Binary Data: ON
Keep Only Set: OFF
```

Dacă ai probleme, scoate temporar node-ul și leagă direct:

```text
Download New Google Drive File → Supabase Vector Store - Insert
```

---

### 6.4 Default Data Loader

```text
Data Type: Binary
Binary Property: data
```

Acest node trebuie să primească text splitter:

```text
Recursive Character Text Splitter → Default Data Loader
```

Dacă apare eroarea:

```text
A Text Splitter sub-node must be connected and enabled
```

înseamnă că lipsește conexiunea Text Splitter → Default Data Loader.

---

### 6.5 Recursive Character Text Splitter

Setări recomandate:

```text
Chunk Size: 1000
Chunk Overlap: 200
```

Pentru documente lungi / juridice:

```text
Chunk Size: 1500
Chunk Overlap: 250
```

---

### 6.6 Embeddings Google Gemini / Gemini2

În ambele node-uri setează același model:

```text
models/gemini-embedding-001
```

sau:

```text
gemini-embedding-001
```

Credential:

```text
Google Gemini API key / Google AI Studio API key
```

Nu folosi Google Drive OAuth2 aici.

---

### 6.7 Supabase Vector Store - Insert

```text
Mode: Insert Documents
Table Name: documents
```

Trebuie să aibă 3 intrări:

```text
Main input de la Google Drive Download / Set Metadata
Document input de la Default Data Loader
Embeddings input de la Embeddings Google Gemini2
```

---

### 6.8 Supabase Vector Store - RAG Tool

```text
Mode: Retrieve as Tool
Tool Name: company_knowledge_base
Table Name: documents
Query Name: match_documents
Top K: 5
```

Trebuie conectat ca tool la AI Agent.

---

### 6.9 OpenRouter Chat Model

```text
Credential: OpenRouter API key
Model: openai/gpt-4o-mini
Temperature: 0.2
```

---

### 6.10 AI Agent

System message recomandat:

```text
Ești un asistent RAG. Răspunde folosind informațiile găsite în Supabase Vector Store. Dacă nu găsești răspunsul în documente, spune clar că informația nu există în baza de cunoștințe.
```

---

## 7. Ordinea de testare

### Pasul 1 — testează Google Drive

Urcă un fișier `.pdf`, `.docx` sau `.txt` în folderul Google Drive.

Rulează workflow-ul sau așteaptă triggerul.

Verifică în n8n la **Download New Google Drive File** că apare:

```text
Binary → data
```

---

### Pasul 2 — testează inserarea în Supabase

După rulare, verifică în Supabase:

```sql
select id, left(content, 100) as preview, metadata
from documents
order by id desc
limit 10;
```

Dacă apar rânduri, documentul a fost indexat.

---

### Pasul 3 — testează RAG Chat

În chat-ul n8n întreabă ceva din documentul încărcat, de exemplu:

```text
Ce spune documentul despre procedura de inspecție?
```

Dacă AI Agent răspunde folosind documentul, setup-ul este corect.

---

## 8. Erori frecvente și rezolvare

### 8.1 `invalid_grant`

Problemă Google OAuth.

Rezolvare:

```text
1. Șterge credentialul Google Drive din n8n
2. Creează-l din nou
3. Copiază exact OAuth Redirect URL din n8n
4. Pune-l în Google Cloud la Authorized redirect URIs
5. Apasă Connect / Reconnect
```

---

### 8.2 `This operation expects the node's input data to contain a binary file 'data'`

Default Data Loader caută binary `data`, dar nu există.

Verifică:

```text
Download New Google Drive File → Binary Property: data
Default Data Loader → Binary Property: data
```

Dacă există node **Set File Metadata**, verifică:

```text
Keep Binary Data: ON
Keep Only Set: OFF
```

Sau scoate temporar Set File Metadata.

---

### 8.3 `A Text Splitter sub-node must be connected and enabled`

Lipsește text splitter-ul.

Conectare corectă:

```text
Recursive Character Text Splitter → Default Data Loader
Default Data Loader → Supabase Vector Store - Insert
```

---

### 8.4 `expected 768 dimensions, not 3072`

Supabase este setat pe `vector(768)`, dar Gemini trimite `3072` dimensiuni.

Rezolvare:

```text
Schimbă tabelul și funcția match_documents pe vector(3072)
```

Folosește SQL-ul din secțiunea 4.

---

### 8.5 `column reference "metadata" is ambiguous`

Funcția SQL este scrisă fără alias.

Rezolvare:

În funcția `match_documents`, folosește:

```sql
d.metadata
```

nu doar:

```sql
metadata
```

SQL-ul corect este în secțiunea 4.

---

## 9. Checklist final pentru stația nouă

Bifează în ordine:

```text
[ ] n8n instalat / pornit
[ ] workflow.json importat
[ ] Google Drive OAuth2 creat și conectat
[ ] Google Drive API activat în Google Cloud
[ ] Redirect URI n8n pus corect în Google Cloud
[ ] Gemini API key creat și pus în ambele noduri de embeddings
[ ] OpenRouter API key creat și pus în OpenRouter Chat Model
[ ] Supabase credential creat cu service_role key
[ ] SQL Supabase rulat cu vector(3072)
[ ] Folder ID Google Drive setat corect
[ ] Download node are Binary Property = data
[ ] Default Data Loader are Binary Property = data
[ ] Recursive Character Text Splitter este conectat la Default Data Loader
[ ] Supabase Insert are document + embeddings conectate
[ ] Supabase RAG Tool are embeddings conectate
[ ] AI Agent are OpenRouter Chat Model și Supabase Tool conectate
[ ] Test cu fișier nou în Google Drive
[ ] Verificare rânduri în Supabase documents
[ ] Test întrebare în chat
```

---

## 10. Recomandare de lucru

Pentru test inițial, urcă un singur fișier mic `.docx` sau `.txt`.

După ce merge tot fluxul, poți urca PDF-uri și documente mai mari.

Dacă urci multe fișiere deodată, Google Drive Trigger poate rata unele fișiere. Pentru producție, e mai sigură varianta cu:

```text
Schedule Trigger
↓
Google Drive List/Search files
↓
Loop Over Items
↓
Download fiecare fișier
↓
Insert în Supabase
```

create extension if not exists vector;

drop table if exists documents;

create table documents (
  id bigserial primary key,
  content text,
  metadata jsonb,
  embedding vector(3072)
);

create or replace function match_documents (
  query_embedding vector(3072),
  match_count int default 5,
  filter jsonb default '{}'
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from documents d
  where d.metadata @> filter
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;
