# Phase 3 Enhancements: Video Collections & Organization

**Status**: Planning
**Last Updated**: 2025-12-03
**Target**: Improve video organization with collections, tags, and flexible conversation creation

---

## Overview

Enhance the RAG Transcript system with hierarchical video organization through Collections, allowing users to group related videos (e.g., by course, instructor, subject) and create conversations with flexible video selection.

---

## Features

### 1. Video Collections (Playlists)

**Description**: Organize videos into collections with metadata

**Structure**:
```
Collection
├─ Videos (many-to-many relationship)
└─ Metadata (instructor, subject, tags, etc.)
```

**Key Points**:
- Videos can belong to multiple collections
- Collections can be shared between users (Phase 4)
- Default "Uncategorized" collection for new videos
- Unlimited videos per collection

### 2. Flexible Conversation Creation

**Three Selection Modes**:

1. **Collection-based**: Chat with entire collection
2. **Multi-select**: Cherry-pick individual videos
3. **Single video**: Quick focused conversation

### 3. Metadata & Organization

**Collection Metadata**:
- Name (required)
- Description (optional)
- Instructor name
- Subject/Topic
- Semester/Period
- Custom tags (array)

**Video Tags**:
- Custom labels (#midterm-prep, #advanced, etc.)
- Multi-select filtering

### 4. Advanced Features

**Search & Filter**:
- Filter by: Subject, Instructor, Collection, Status, Tags
- Full-text search across titles and descriptions

**Bulk Operations**:
- Add multiple videos to collection
- Import entire YouTube playlists → auto-create collection
- Batch tagging

**Smart Suggestions** (Future):
- Videos not yet chatted with
- Related videos based on content
- Auto-suggest collections based on video titles

---

## Database Schema

### New Tables

#### `collections`
```sql
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',  -- {instructor, subject, semester, tags[]}
    is_default BOOLEAN DEFAULT FALSE,  -- For "Uncategorized" collection
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_user_default UNIQUE (user_id, is_default) WHERE is_default = TRUE
);

CREATE INDEX idx_collections_user_id ON collections(user_id);
CREATE INDEX idx_collections_metadata ON collections USING GIN(metadata);
```

#### `collection_videos` (Join Table)
```sql
CREATE TABLE collection_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT NOW(),
    added_by_user_id UUID REFERENCES users(id),
    position INTEGER,  -- For custom ordering within collection

    CONSTRAINT unique_collection_video UNIQUE (collection_id, video_id)
);

CREATE INDEX idx_collection_videos_collection ON collection_videos(collection_id);
CREATE INDEX idx_collection_videos_video ON collection_videos(video_id);
```

#### `collection_members` (For Sharing - Phase 4)
```sql
CREATE TABLE collection_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    added_at TIMESTAMP DEFAULT NOW(),
    added_by_user_id UUID REFERENCES users(id),

    CONSTRAINT unique_collection_member UNIQUE (collection_id, user_id)
);

CREATE INDEX idx_collection_members_collection ON collection_members(collection_id);
CREATE INDEX idx_collection_members_user ON collection_members(user_id);
```

### Modified Tables

#### `videos` (Add tags column)
```sql
ALTER TABLE videos ADD COLUMN tags TEXT[] DEFAULT '{}';
CREATE INDEX idx_videos_tags ON videos USING GIN(tags);
```

---

## API Endpoints

### Collections

```
POST   /api/v1/collections                    - Create collection
GET    /api/v1/collections                    - List user's collections
GET    /api/v1/collections/{id}               - Get collection details (with videos)
PATCH  /api/v1/collections/{id}               - Update collection
DELETE /api/v1/collections/{id}               - Delete collection

POST   /api/v1/collections/{id}/videos        - Add videos to collection
DELETE /api/v1/collections/{id}/videos/{vid}  - Remove video from collection

GET    /api/v1/collections/{id}/chat          - Create conversation with collection videos
```

### Videos (Enhanced)

```
PATCH  /api/v1/videos/{id}/tags               - Update video tags
GET    /api/v1/videos?collection_id={id}      - Filter videos by collection
GET    /api/v1/videos?tags={tag1,tag2}        - Filter by tags
```

### Conversations (Enhanced)

```
POST   /api/v1/conversations                  - Enhanced with collection_id support
  Body: {
    "title": "string",
    "collection_id": "uuid",      // NEW: Select all videos from collection
    "selected_video_ids": [],     // OR: Select specific videos
  }
```

---

## UI Components

### 1. Videos Page Redesign

**Layout**:
```
┌──────────────────────────────────────────────────┐
│ Videos                 [+ New Collection]        │
│                                                   │
│ [Search...] [Filter: All ▼] [Sort: Recent ▼]    │
├──────────────────────────────────────────────────┤
│                                                   │
│ 📁 Machine Learning Course (12 videos)          │
│    Instructor: Dr. Ng | Subject: AI              │
│    Tags: #course #ai #2024                       │
│    [Chat with All] [Manage] [⋮]                 │
│                                                   │
│    Expanded view:                                │
│    ├─ ✓ Intro to ML          [Chat] 45:30       │
│    ├─ ✓ Linear Regression    [Chat] 52:15       │
│    └─ ⏳ Neural Networks      processing          │
│                                                   │
│ 📁 Physics 101 (8 videos)                       │
│    Instructor: Prof. Feynman | Subject: Physics  │
│    [Chat with All] [Manage] [⋮]                 │
│                                                   │
│ 📂 Uncategorized (3 videos)                     │
│    └─ Random video [Chat] [Add to Collection]   │
└──────────────────────────────────────────────────┘
```

### 2. Create Collection Modal

```
┌─────────────────────────────────────────┐
│ Create Collection                       │
├─────────────────────────────────────────┤
│ Name*:                                  │
│ [Machine Learning Course_________]      │
│                                         │
│ Description:                            │
│ [Stanford CS229 lectures________]       │
│                                         │
│ Metadata (optional):                    │
│ Instructor: [Dr. Andrew Ng_______]      │
│ Subject:    [Computer Science____]      │
│ Semester:   [Fall 2024___________]      │
│                                         │
│ Tags:                                   │
│ [#course] [#ai] [+ Add tag]            │
│                                         │
│         [Cancel]    [Create]            │
└─────────────────────────────────────────┘
```

### 3. Enhanced Conversation Creation

```
┌─────────────────────────────────────────┐
│ New Conversation                        │
├─────────────────────────────────────────┤
│ Select videos:                          │
│                                         │
│ ⚪ Entire Collection                    │
│    [Machine Learning Course ▼]          │
│    12 videos will be included           │
│                                         │
│ ⚪ Custom Selection                     │
│    Collections:                         │
│    ☐ Machine Learning (12 videos)      │
│      ☑ Intro to ML                     │
│      ☑ Linear Regression               │
│      ☐ Neural Networks                 │
│                                         │
│ Title (optional):                       │
│ [Auto-generated based on selection]    │
│                                         │
│         [Cancel]    [Create Chat]       │
└─────────────────────────────────────────┘
```

### 4. Video Upload Flow

```
After clicking "Ingest Video":

┌─────────────────────────────────────────┐
│ Add to Collection                       │
├─────────────────────────────────────────┤
│ ⚪ Add to existing collection:          │
│    [Select collection ▼]                │
│                                         │
│ ⚪ Create new collection:               │
│    Name: [New Course__________]         │
│                                         │
│ ⚪ Leave uncategorized                  │
│                                         │
│         [Skip]    [Add Video]           │
└─────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 3.1: Core Collections (Week 1)
- [ ] Database schema migration
- [ ] Backend models (Collection, CollectionVideo)
- [ ] API endpoints (CRUD collections)
- [ ] Frontend: Collection list view
- [ ] Frontend: Create/edit collection modal
- [ ] Frontend: Add videos to collection
- [ ] Create conversations from collections

### Phase 3.2: Enhanced Organization (Week 2)
- [ ] Tags system for videos
- [ ] Search and filter UI
- [ ] Bulk video operations
- [ ] Reorder videos within collection
- [ ] Collection analytics (video count, total duration)

### Phase 3.3: Smart Features (Week 3)
- [ ] YouTube playlist import
- [ ] Auto-suggest collections based on video titles
- [ ] "Uncategorized" videos reminder
- [ ] Collection templates
- [ ] Export collection metadata

### Phase 4: Sharing & Collaboration (Future)
- [ ] Collection sharing (owner/editor/viewer roles)
- [ ] Invite links
- [ ] Shared conversation permissions
- [ ] Activity feed for shared collections

---

## Design Decisions

### 1. **Collections vs. Tags**
- **Collections**: Primary grouping (like folders)
- **Tags**: Cross-cutting labels for filtering
- Videos can have both

### 2. **Default "Uncategorized" Collection**
- Every user gets auto-created "Uncategorized" collection
- Cannot be deleted (can be hidden if empty)
- Videos without collection assignment go here

### 3. **Many-to-Many Relationship**
- Videos can belong to multiple collections
- Example: "Lecture 5" in both "Full Course" and "Midterm Review" collections

### 4. **Storage Accounting**
- Video storage counted toward uploader only
- Collections are metadata (negligible size)
- Shared collections don't duplicate storage

### 5. **Conversation Video Selection**
- Always show individual video checkboxes
- Collections are shortcuts for bulk selection
- User can always override and customize

---

## Questions & Decisions

### Answered:
- ✅ Collection ownership: Can be shared (Phase 4)
- ✅ Video limits: Unlimited
- ✅ Multiple collections: Yes, videos can belong to many
- ✅ Upload default: Prompt for collection, default to "Uncategorized"
- ✅ Priority: All features important

### Open Questions:
1. Should collection names be unique per user?
2. Max number of collections per user? (quota consideration)
3. When deleting a collection, keep videos or cascade delete?
4. Auto-create collections from YouTube playlist titles?
5. Allow nested collections (sub-collections)?

---

## Migration Strategy

### For Existing Users:
1. Create "Uncategorized" collection for each user
2. Add all existing videos to "Uncategorized"
3. Users can then organize into new collections

### For New Users:
1. Auto-create "Uncategorized" collection on signup
2. Show onboarding tour explaining collections

---

## Testing Checklist

- [ ] Create collection
- [ ] Add/remove videos from collection
- [ ] Delete collection (keeps videos)
- [ ] Videos in multiple collections
- [ ] Create conversation from collection
- [ ] Create conversation with mixed selection
- [ ] Filter/search videos by collection
- [ ] Tags CRUD operations
- [ ] Bulk video operations
- [ ] YouTube playlist import
- [ ] Permissions (owner can edit, others cannot)

---

## Future Enhancements (Post-Phase 3)

- AI-powered collection suggestions based on video content
- Automatic tagging from video transcripts
- Collection templates (Course, Conference, Tutorial series)
- Export collection as JSON/CSV
- Duplicate detection across collections
- Collection merge functionality
- Version history for collections
