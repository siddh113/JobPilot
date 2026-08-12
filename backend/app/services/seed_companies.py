"""A seed list of well-known companies to auto-resolve against Greenhouse,
Lever, Ashby, and SmartRecruiters (see app/services/resolver.py). This is
what replaces manually adding companies one at a time — run
`discover-companies` and it tries all of these (plus any you've already
added) and keeps whichever ones actually resolve to a live board.

This is a starting list, not exhaustive — add names to SEED_COMPANIES as
you think of companies you want covered, no token lookup needed. Workday
companies are deliberately excluded from this list (see CLAUDE.md §0/§5) —
add those manually with the real careers URL if you want one.
"""

SEED_COMPANIES = [
    # Already-verified core set
    "Figma", "Datadog", "Squarespace", "Databricks", "Robinhood", "Stripe",
    "Airbnb", "Coinbase", "Brex", "Plaid", "Affirm", "Notion", "Ramp",
    "Perplexity",
    # Additional candidates worth trying — not all will resolve, that's fine
    "Scale AI", "Anysphere", "Vercel", "Linear", "Retool", "Rippling",
    "Deel", "Mercury", "Chime", "Gusto", "Carta", "Segment", "Twitch",
    "Asana", "Dropbox", "Instacart", "DoorDash", "Reddit", "Discord",
    "Cloudflare", "MongoDB", "Confluent", "HashiCorp", "GitLab", "Postman",
    "Airtable", "Miro", "Loom", "Webflow", "Framer", "Replit", "Modal",
    "Together AI", "Anthropic", "OpenAI", "Hugging Face", "Weights and Biases",
    "Pinecone", "LangChain", "Sierra", "Harvey", "Glean",
    # SmartRecruiters tends to skew larger/enterprise
    "Visa", "Bosch", "Skechers", "McDonald's", "Groupon",
    # Earlier-stage / true startups — smaller teams, higher risk/reward,
    # often move faster on hiring decisions than the larger names above
    "Cognition", "Cribl", "Mintlify", "Decagon", "Clay", "Attio", "Vanta",
    "Windsurf", "Fireworks AI", "Baseten", "Replicate", "Runway",
    "ElevenLabs", "Character.AI", "Abridge", "Ambience Healthcare",
    "Applied Intuition", "Cresta", "Speak", "Sigma Computing", "Statsig",
    "LaunchDarkly", "Temporal", "Neon", "Supabase", "PlanetScale",
    "Cockroach Labs", "Redpanda", "Grafana Labs", "Chronosphere",
    "ClickHouse", "dbt Labs", "Airbyte", "Fivetran", "Hex", "PostHog",
    "Bland AI", "Multiverse",
]
