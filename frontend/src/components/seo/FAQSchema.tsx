// FAQ data exported for reuse
export const faqData = [
  {
    question: "What's included in the free tier?",
    answer:
      'The free tier includes 10 videos, 200 messages per month, 1 GB storage, and 1000 minutes of transcription per month. Perfect for trying out the platform and small projects.',
  },
  {
    question: 'Can I upgrade anytime?',
    answer:
      'Yes! You can upgrade to Pro or Enterprise anytime. Your quota increases immediately, and you only pay for the remaining time in the billing period.',
  },
  {
    question: 'What happens to my data if I cancel?',
    answer:
      'Your data remains accessible for 30 days after cancellation. You can export your transcripts and conversations anytime. After 30 days, data is permanently deleted.',
  },
  {
    question: 'Do you offer refunds?',
    answer:
      "Yes, we offer a 14-day money-back guarantee for all paid plans. If you're not satisfied, contact us for a full refund within 14 days of purchase.",
  },
  {
    question: 'Is my data secure?',
    answer:
      'Absolutely. All data is encrypted in transit and at rest. We use industry-standard security practices and never share your data with third parties. Your videos and transcripts are private.',
  },
  {
    question: 'Can I export my data?',
    answer:
      'Yes! Transcripts can be downloaded as plain text with timestamps and speaker labels from the videos page. We are actively working on conversation export features.',
  },
  {
    question: 'What AI models do you use?',
    answer:
      'We use proprietary AI for transcription, state-of-the-art models for semantic search, and advanced language models for conversations.',
  },
  {
    question: 'What video sources do you support?',
    answer:
      'Currently we support YouTube videos including public videos, unlisted videos (with URL), and videos with captions. Support for Vimeo, direct video uploads, and podcast RSS feeds is on our roadmap.',
  },
  {
    question: 'How accurate is the transcription?',
    answer:
      'Our AI transcription achieves approximately 95% accuracy for clear English audio. When YouTube captions are available, we use those for even faster processing. You can always view and verify the full transcript.',
  },
  {
    question: 'Can I search across multiple videos at once?',
    answer:
      'Yes! You can organize videos into collections and search across all videos in a collection simultaneously. This is perfect for course materials, research projects, or training libraries.',
  },
  {
    question: 'What makes Reasoner mode different from Chat mode?',
    answer:
      'Chat mode gives fast, direct answers to straightforward questions. Reasoner mode uses step-by-step chain-of-thought reasoning, making it ideal for complex analysis, finding patterns across sources, or questions requiring deeper synthesis. Reasoner mode is available on Pro plans.',
  },
  {
    question: 'How does conversation memory work?',
    answer:
      'After 15+ messages in a conversation, our AI automatically extracts and stores key facts, entities, and context from your discussion. These facts persist across sessions, so when you return to a conversation days later, the AI remembers what you discussed, what conclusions you reached, and what topics matter to you. This enables truly long-running research conversations without losing context.',
  },
  {
    question: 'Is there an API available?',
    answer:
      'API access is on our roadmap. If you have specific integration needs for your team or product, please contact us to discuss early access or custom solutions.',
  },
]

export default function FAQSchema() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqData.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  }

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  )
}
