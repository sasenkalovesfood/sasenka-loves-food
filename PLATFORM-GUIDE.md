# Moving this site to a no-code platform

You asked about a platform where you can add new reviews visually, without touching code. Here's what I'd recommend and why, and exactly how to rebuild the design you now have.

## My top pick: Squarespace

Squarespace is the best balance of "drag-and-drop easy" and "will actually look like my brand" for what you're doing. Every review can be a blog post, which gives you:

- A proper "review index" page built automatically from your posts
- A dedicated page for each review, with a consistent layout
- Tags and categories (cuisine, city, price band) that generate filtered pages for free
- A decent phone-first editor for when you're writing on the go

Expected cost: around &pound;14-22/month on the Personal or Business plan, plus a domain (~&pound;12/year).

### Why not the alternatives

- **Wix** is more flexible but fiddlier, and tends to tempt you into layout decisions you'll regret. Not worth the extra freedom for a review blog.
- **Ghost** has beautiful typography and is loved by food writers, but their editor is less forgiving if you want photo galleries and sidebars mixed into each post. Worth considering if you ever want a paid newsletter tier.
- **WordPress** is powerful and cheap if self-hosted, but the setup and ongoing admin is more than you want.
- **Notion + Super.so** is the cheapest and fastest to set up, but you'll lose some of the heavier typographic personality that makes your brand feel like your brand.

## How to rebuild this design on Squarespace

Keep the HTML prototype open on one screen while you do this, and copy-paste where you can.

### 1. Pick a template

Start with **Hester** or **Tudor**. Both are image-forward with strong typography and a magazine-style blog layout. Hester is closer to what I've built.

### 2. Set your brand colours

Design > Colors > Edit Palette, then paste in:

- Background: `#48453B`
- Primary text: `#F3EEE1`
- Accent: `#BD112E`
- Secondary/card background: `#534F44`

Pick "Darkest" as your default theme so the olive sits behind everything.

### 3. Set your fonts

Design > Fonts > Base. Use **Bowlby One** for headings (or **Archivo Black** if they don't have Bowlby) and **Inter** for body text. If you want the handwritten accents like "Not gospel, just gut feeling," enable **Caveat** as a custom font.

### 4. Upload your logo

I've saved your wordmark as `assets/wordmark.svg`. Go to Design > Logo & Title and upload it as the site logo. It will scale correctly on mobile.

### 5. Build the "Rating system" page

Pages > Add Page > Blank. Copy the text from `rating-system.html` section by section. Use a "Text" block for paragraphs and a "Table" block (or a 2-column Gallery) for the five-element table.

### 6. Turn reviews into blog posts

Pages > Add Page > Blog. Set the blog URL to `/reviews`. For each review:

- **Title**: Restaurant name
- **Categories**: Cuisine (e.g. "Italian")
- **Tags**: City, price band
- **Featured image**: the hero photo
- **Body**: paste the written review, break it into Text blocks, and use a **Divider + Quote block** for the pull quotes
- Use a **5-column Gallery** at the top for the scores. Each column is a text block styled like the `.score` cards in my version: label on top, big number underneath.
- Use a **Gallery block** at the bottom for "From the meal"

### 7. Copy the sidebar "facts"

The address / cuisine / price / date panel is easiest as a single **Text block** with a table layout, placed just under the title. You can also use the Squarespace "Summary" custom fields if you want the facts to display in the review index automatically.

### 8. Point your domain

Buy the domain through Squarespace (cleanest) or point an existing one. If you want `sasenkalovesfood.com`, register it at the Settings > Domains step.

## If you want to keep this HTML version too

This is a complete working site. You can host it for free on:

- **Netlify**: drag the whole folder onto their dashboard (netlify.com/drop), done in 30 seconds, gives you a free URL
- **GitHub Pages**: if you're willing to make one GitHub account
- **Cloudflare Pages**: free, fast, takes about 2 minutes

This is useful as a fallback or while you set up Squarespace. No code changes required.

## What I'd do if I were you

1. This week: drop the HTML folder onto Netlify so you have a live link you can share.
2. Next week: start a Squarespace trial (14 days free), spend an afternoon rebuilding the homepage and the rating system page.
3. Weekend after: migrate 3-4 existing Instagram reviews across as blog posts. Use the captions as a starting draft, expand the written portion, pull in the photos, fill in the five scores.
4. After that: a new review once a month, posted to Squarespace first, repurposed to Instagram after.

Happy to help you through any of the above.
