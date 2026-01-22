# Phase 1 Citation Enhancement - User Guide

## What's New

Your conversation citations now show **who said it**, **where it's from**, and **which section** of the video!

## New Citation Information

### 1. Channel Name 📺
See which YouTube channel the information comes from without opening the video.

**Example:**
```
Source 1: React Hooks Explained     02:05 - 03:00     95% match
📺 React Tutorial Channel
```

### 2. Chapter Titles 📖
Know which section of the video the citation refers to (for videos with chapters).

**Example:**
```
Source 2: Advanced React Patterns    15:30 - 18:45    92% match
📺 FrontendMasters    📖 Introduction to Hooks
```

### 3. Speaker Attribution 🎤
See who said what in multi-speaker videos like interviews or panels (when available).

**Example:**
```
Source 3: React Conference Talk      25:10 - 27:30    88% match
📺 ReactConf    📖 Q&A Session    🎤 Dan Abramov, Ryan Florence
```

## Where You'll See This

### Source Cards (Below AI Responses)

Each source citation now shows:
```
┌─────────────────────────────────────────────────────────────┐
│ Source 1  React Hooks Explained    02:05 - 03:00   95% match│
│ 📺 React Tutorial Channel  📖 Introduction to Hooks          │
│ "React hooks allow you to use state and other React..."     │
│ [Jump to video]                                              │
└─────────────────────────────────────────────────────────────┘
```

### Citation Badges (Inline [1] [2] [3])

Click on any inline citation badge like `[1]` to see expanded details:

```
┌─────────────────────────────────────┐
│ Source: React Hooks Explained    ✕ │
│ Citation 1                          │
│ 📺 React Tutorial Channel           │
│ 📖 Introduction to Hooks            │
│ ─────────────────────────────────── │
│ ⏱ 02:05 - 03:00 →                  │
│ Click to jump to video timestamp    │
│ ─────────────────────────────────── │
│ Relevance: 95%                      │
│ ████████████████████░░ 95%          │
│ ─────────────────────────────────── │
│ "React hooks allow you to use..."  │
└─────────────────────────────────────┘
```

### Working Timestamp Links! ✨

**FIXED:** The timestamp button in citation badges now actually works!

- Click the timestamp in the expanded citation badge
- YouTube opens at the exact moment the quote comes from
- Verify citations instantly without searching through videos

## How to Use

### Verify a Citation

1. Look for inline citations in AI responses: `[1]`, `[2]`, etc.
2. Click the badge to see full context
3. Check the channel name and chapter to confirm it's relevant
4. Click the timestamp to watch the exact moment in the video

### Jump to a Video Section

1. Scroll to the source cards below each AI response
2. Find the source you want to verify
3. Click "Jump to video" button
4. YouTube opens at the exact timestamp

### Understand Multi-Speaker Content

When videos have multiple speakers (coming soon with enhanced transcription):
- See who contributed which information
- Distinguish between interviewer and interviewee
- Identify expert opinions vs. questions

## Benefits

✅ **Transparency** - Know exactly where information comes from
✅ **Verification** - Click through to verify AI responses
✅ **Context** - Understand which part of the video was cited
✅ **Trust** - See the full picture behind each citation
✅ **Efficiency** - Find relevant content without watching entire videos

## Example Conversation Flow

**You:** "What are the main benefits of React hooks?"

**AI:** "React hooks provide several key benefits [1] [2]:

1. **Simplified State Management**: Hooks eliminate the need for class components, making it easier to manage state in functional components [1].

2. **Better Code Reusability**: Custom hooks allow you to extract and reuse stateful logic across components [2].

3. **Improved Readability**: Hook-based code tends to be more concise and easier to understand [1]."

**Source Cards:**
```
┌─────────────────────────────────────────────────────────────┐
│ Source 1  React Hooks Explained      02:05 - 03:00  95% match│
│ 📺 React Tutorial Channel  📖 Introduction to Hooks          │
│ "React hooks allow you to use state and other React..."     │
│ [Jump to video]                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Source 2  Advanced React Patterns   15:30 - 18:45  92% match│
│ 📺 FrontendMasters  📖 Custom Hooks Pattern                  │
│ "One of the most powerful aspects of hooks is the..."       │
│ [Jump to video]                                              │
└─────────────────────────────────────────────────────────────┘
```

## Notes

- **Graceful Degradation**: If a video doesn't have chapter titles or speaker labels, those fields simply won't appear
- **No Clutter**: Only shows information that's actually available
- **Always Up-to-Date**: New conversations automatically include this metadata
- **Existing Conversations**: Old conversations will show new metadata when you reload the page

## Feedback

If you notice any issues or have suggestions for improvement, please let us know!

---

**Ready for Phase 2?** Next up: Embedded video player so you can watch videos without leaving the conversation page!
