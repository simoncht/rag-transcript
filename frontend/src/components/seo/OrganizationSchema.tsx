export default function OrganizationSchema() {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://frontend-production-9252.up.railway.app'

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'RAG Transcript',
    url: baseUrl,
    logo: `${baseUrl}/logo.png`,
    description: 'AI-powered video knowledge base with semantic search. Transform YouTube videos into searchable knowledge.',
    contactPoint: {
      '@type': 'ContactPoint',
      email: 'support@ragtranscript.com',
      contactType: 'customer support',
    },
  }

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  )
}
