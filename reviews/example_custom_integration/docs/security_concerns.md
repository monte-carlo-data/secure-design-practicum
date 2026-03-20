# Known Security Concerns

- Customer-authored Jinja2 templates are rendered server-side on the backend
- Custom connector runtimes run in customer cloud accounts but communicate with a hosted ingestion service
- A new connector definition model allows customers to define their own collection behavior
