export default function SoftwareSchema() {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://frontend-production-9252.up.railway.app'

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'RAG Transcript',
    applicationCategory: 'ProductivityApplication',
    operatingSystem: 'Web',
    url: baseUrl,
    description: 'AI-powered video transcription and semantic search platform. Transform YouTube videos into a searchable knowledge base with chat capabilities.',
    featureList: [
      'AI-powered video transcription',
      'Semantic search across video content',
      'Chat with your videos using RAG technology',
      'Timestamped citations and source references',
      'Collection management for organizing videos',
      'Conversation memory for long-running research',
    ],
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      lowPrice: '0',
      highPrice: '79.99',
      offerCount: '3',
      offers: [
        {
          '@type': 'Offer',
          name: 'Free',
          price: '0',
          priceCurrency: 'USD',
          description: '10 videos, 200 messages/month, 1 GB storage',
        },
        {
          '@type': 'Offer',
          name: 'Pro',
          price: '23.99',
          priceCurrency: 'USD',
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: '23.99',
            priceCurrency: 'USD',
            billingDuration: 'P1M',
          },
          description: 'Unlimited videos and messages, 50 GB storage',
        },
        {
          '@type': 'Offer',
          name: 'Enterprise',
          price: '79.99',
          priceCurrency: 'USD',
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: '79.99',
            priceCurrency: 'USD',
            billingDuration: 'P1M',
          },
          description: 'Unlimited videos, messages, and storage',
        },
      ],
    },
  }

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  )
}
