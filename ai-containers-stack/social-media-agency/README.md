# Social Media Agency workflows

Curated n8n workflow sources imported from
[`iuliandevct/social_media_agency`](https://github.com/iuliandevct/social_media_agency)
at commit `37b4254`.

Included:

- LeeWu Maritime image prompt, image generation, and Sheets workflow;
- YouTube Generator workflow;
- full YouTube chat and video pipeline workflow.

The upstream `docker-compose.yml` was deliberately not copied because it embeds
default passwords and an InfluxDB token. The sample MP4 was also excluded from
the operational stack. Import workflow JSON files into the existing n8n instance
only after reviewing credential references and replacing them with local n8n
credentials.

The Second Brain reports this module as online when the upstream checkout exists
at `~/Documents/social_media_agency/.git`. Override that location with the
`SOCIAL_MEDIA_AGENCY_PATH` environment variable used by the graph API.
