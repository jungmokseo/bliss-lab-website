# BLISS Lab Website v2

Complete single-page HTML website for BLISS Lab at Yonsei University.

## File Structure

```
bliss-website-v2/
├── index.html                   # Main website (single-page, 1169 lines)
├── data/
│   ├── publications.json       # Publication data (8 entries)
│   └── team.json              # Team member data (PI + 10 members)
├── original-reference.html     # Reference design file
└── images/
    └── team/                   # Team member photos (referenced but optional)
```

## Key Features

### 1. Hero Section
- Two-column layout with custom inline SVG
- Bio-electronic circuit aesthetic with light blue traces
- Biological cell shapes and nodes overlapping
- Gradient background (#E8EFFE to white)
- Smooth scroll animations

### 2. Research Areas
- 4-card grid with color-coded research topics:
  - Hydrogels (#0055FF)
  - Bio-Adhesives (#D84315)
  - Antifouling (#00897B)
  - Liquid Metal (#6A1B9A)
- Hover effects and reveal animations

### 3. Research Highlights
- Alternating image/content cards
- Problem-Technology-Application framework
- Icon-based significance indicators

### 4. Publications (Data-Driven)
- Accordion-style year grouping
- Fetches from `data/publications.json`
- Fallback to static content if JSON unavailable
- Expandable/collapsible year groups

### 5. Team (Data-Driven)
- PI section with photo/bio layout
- Ph.D. and M.S. student grids
- Modal popup on click with member details
- Fetches from `data/team.json`
- Supports images from `images/team/` folder

### 6. News + Updates
- Featured card with alternating grid layout
- 5 news items with tags and metadata

### 7. Contact Section
- Multi-row contact information
- Map embed placeholder
- Address, email, phone, department

### 8. Language Toggle
- EN/KR toggle button in navigation
- Default English display
- All content has data-kr and data-en attributes
- Dynamic language switching

### 9. Navigation
- Fixed sticky header with blur effect
- Smooth scroll links
- Hamburger menu for mobile
- Language toggle

### 10. Responsive Design
- Desktop: Full multi-column layouts
- Tablet (1024px): Single/dual columns
- Mobile (768px): Hamburger menu
- Small mobile (480px): Single column, stacked buttons

## CSS Styling Details

### Color Scheme
```
--accent: #0055FF
--accent-soft: #E8EFFE
--bg: #FAFAFA
--white: #FFFFFF
--text-primary: #1A1A1A
--text-secondary: #555555
--text-muted: #999999
--border: #E5E5E5
--border-light: #F0F0F0
```

### Typography
- **Playfair Display**: Headlines (Serif)
- **Space Grotesk**: Logo, accents (Monospace)
- **Inter**: Body text (Sans-serif)
- **Pretendard**: Korean text (Sans-serif)

### Features
- Scroll reveal animations with staggered delays
- Smooth transitions on all interactive elements
- Drop shadows for depth
- Rounded corners (6-16px radius)
- Backdrop blur on navigation
- Scroll-responsive navbar styling

## JavaScript Features

1. **Navigation**
   - Sticky scroll detection
   - Hamburger menu toggle
   - Smooth scroll to anchors

2. **Language Toggle**
   - Toggle between English and Korean
   - Updates all `[data-kr][data-en]` elements
   - Persists across page interactions

3. **Publications**
   - Fetches from JSON with fallback
   - Groups by year (descending)
   - Accordion expand/collapse
   - First year opens by default

4. **Team**
   - Fetches from JSON with fallback
   - Renders PI + categorized members
   - Modal popup with member details
   - Fallback to static data if JSON unavailable

5. **Animations**
   - Intersection Observer for reveal animations
   - Staggered transitions with delay classes
   - Hover effects on cards

## JSON Data Files

### publications.json
```json
{
  "publications": [
    {
      "year": 2026,
      "title": "...",
      "authors": "...",
      "journal": "..."
    }
  ]
}
```

### team.json
```json
{
  "pi": { ... },
  "categories": [ ... ],
  "members": [ ... ]
}
```

## How to Use

1. **Static Deployment**: Open `index.html` in a browser directly
2. **With Server**: Serve with any HTTP server for JSON loading:
   ```bash
   python -m http.server 8000
   # or
   npx http-server
   ```

3. **Adding Team Photos**:
   - Place images in `images/team/` folder
   - Use format: `images/team/{member-id}.jpg`
   - Photos are optional; initials display as fallback

4. **Updating Publications**:
   - Edit `data/publications.json` and add new entries
   - Will auto-populate in accordion by year

5. **Updating Team**:
   - Edit `data/team.json`
   - Add members to appropriate categories
   - Add photos to `images/team/` (optional)

## Production Checklist

- [x] All CSS preserved from reference exactly
- [x] Color scheme verified (#0055FF accent, #FAFAFA background)
- [x] Font families included (Inter, Playfair Display, Space Grotesk, Pretendard)
- [x] Inline SVG hero image (no external file)
- [x] Data-driven Publications (fetch + fallback)
- [x] Data-driven Team (fetch + fallback)
- [x] Language toggle (EN/KR)
- [x] Scroll reveal animations
- [x] Modal team member popup
- [x] Responsive design
- [x] Font Awesome 6.4.0 icons
- [x] Single HTML file (all CSS/JS included)

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

## File Size

- index.html: 63 KB
- publications.json: ~2 KB
- team.json: ~4 KB

## Notes

- The SVG hero image is optimized for 560px width, 480px height
- All animations use CSS transitions and IntersectionObserver (GPU-accelerated)
- JSON fetch is asynchronous with graceful fallback to static content
- Korean language defaults to ON (toggle to EN for English)
- Images in modal/member cards are optional; initials render as fallback
