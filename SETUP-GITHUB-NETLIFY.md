# Publishing the site: GitHub + Netlify setup

A walkthrough for getting `sasenka-loves-food` from your computer to a live website with your own domain.

Total time: about 30 minutes, plus waiting for DNS.

## What you'll have at the end

- Your code backed up on GitHub
- Your site live at your custom domain, with HTTPS
- A flow where any change you make locally appears online within a minute of you pushing it
- The foundation for adding a CMS later

---

## Part A: Put the site on GitHub

### A1. Create a GitHub account

1. Go to https://github.com
2. Click "Sign up"
3. Use `me@sasenka.com` for the email
4. Pick a username. It's public, so keep it clean. Something like `sasenkalovesfood` or `sasenka-lf` is fine.
5. Verify your email

### A2. Install GitHub Desktop

This is the friendly app that handles all the technical bits for you. No command line needed.

1. Go to https://desktop.github.com
2. Download and install for your operating system
3. Open it, sign in with the GitHub account you just created
4. When it asks, choose the option to configure Git with the same name and email as your GitHub account

### A3. Create the repository from your folder

1. In GitHub Desktop, click File → Add Local Repository
2. Click "Choose..." and browse to your `sasenka-loves-food` folder. Select it.
3. GitHub Desktop will say "This directory does not appear to be a Git repository". Click the blue "create a repository" link in that message.
4. A dialogue appears. Fill in:
   - Name: `sasenka-loves-food`
   - Description: "Honest restaurant reviews"
   - Git Ignore: None
   - License: None
5. Click "Create Repository"

You'll now see a long list of files in the left panel. These are all your site files, ready to be committed.

6. At the bottom-left of the window there's a summary box. Type: `Initial site` as the commit message
7. Click the blue "Commit to main" button

### A4. Publish the repository to GitHub

1. Look at the top of the GitHub Desktop window. You'll see a button that says "Publish repository". Click it.
2. A dialogue appears. Fill in:
   - Name: `sasenka-loves-food` (keep it the same)
   - Description: same as before
   - **Untick** "Keep this code private". (Your site files are public anyway once the site is live, and a public repo unlocks free features we want.)
3. Click "Publish repository"

The upload will run in the background. Because the site has lots of photos, this can take a few minutes. When the progress bar disappears, it's done.

4. To check it worked: in your web browser, go to `https://github.com/YOUR_USERNAME/sasenka-loves-food`. You should see all your files listed.

Part A done.

---

## Part B: Connect it to Netlify

### B1. Sign up for Netlify

1. Go to https://www.netlify.com
2. Click "Sign up"
3. Choose "Sign up with GitHub". This links the two accounts cleanly.
4. Authorise Netlify when GitHub asks.

### B2. Import your repository

1. Once logged in to Netlify, you'll land on the dashboard
2. Click "Add new site" (or "Import from Git" if that's what appears)
3. Choose "Deploy with GitHub"
4. Netlify will ask permission to see your repos. Approve.
5. You'll see a list of your GitHub repos. Click `sasenka-loves-food`.

### B3. Configure the build

Netlify will show a "build settings" screen. Because your site is already pre-built HTML, you want:

- Branch to deploy: `main`
- Build command: leave this empty
- Publish directory: `.` (a single full stop, which means "the root folder")

Click "Deploy site" (or "Deploy sasenka-loves-food").

Netlify will do its thing. Give it a minute or two. Once done, the site summary page will show a green "Published" status and a URL that looks something like `https://cheerful-pangolin-12345.netlify.app`. Click that URL to see your site live.

Part B done.

---

## Part C: Test the full loop

This is the moment the whole thing comes together.

1. On your computer, make a small change to the site. For example, open `index.html` in a text editor, change "My latest reviews" to "Latest reviews" (or anything small), save.
2. Open GitHub Desktop. You'll see the change listed.
3. In the commit summary box bottom-left, type something like `Test change`
4. Click "Commit to main"
5. At the top, click "Push origin"
6. Wait about 30 seconds, then refresh your Netlify URL in the browser.

If you see the change live, the full loop works: your folder → GitHub → Netlify → live site.

From now on, anything you change locally and push will publish automatically.

Part C done.

---

## Part D: Custom domain

Once A, B and C are working, we connect your domain.

The high-level idea: you tell your domain registrar to point the domain at Netlify.

### D1. In Netlify

1. Go to your site's dashboard on Netlify
2. Click "Domain management" (or "Domains" in the left nav)
3. Click "Add a domain"
4. Type your domain (e.g. `sasenkalovesfood.com`) and click Verify
5. Netlify will confirm it's not already connected somewhere. Continue.
6. Netlify will give you either two nameservers or a set of DNS records. Write these down or keep the tab open.

### D2. In your domain registrar

This varies slightly by registrar (GoDaddy, Namecheap, Crazy Domains, etc). The general pattern is:

1. Log in to your registrar
2. Find the domain in your account
3. Look for "DNS settings", "DNS management", or "Nameservers"
4. Either:
   - Change the nameservers to the two Netlify provided (simplest), or
   - Add the DNS records Netlify provided, keeping existing nameservers (more fiddly, but you stay in control of DNS)

### D3. Wait

DNS changes take anywhere from 5 minutes to 48 hours to propagate, though usually it's under an hour. Netlify will email you when it kicks in.

Once live, Netlify automatically provisions free HTTPS (a padlock in the browser). You don't have to do anything for that.

Tell me which registrar you used and I'll give you the exact steps for their interface.

---

---

## Part E: Add the CMS (Decap CMS)

Once Part D is done and your site is live at your own domain, we add the CMS so you can write new reviews from a web page instead of touching files.

### How it will work, plain English

You'll visit `sasenkalovesfood.com/admin` in your browser. You log in with an email and password. You see a friendly form: restaurant name, suburb, cuisine, scores, standfirst, body paragraphs, photo uploader, caption for each photo. You fill it in, click publish. Behind the scenes, Decap commits the content to GitHub, Netlify rebuilds the site, and within a minute the new review is live on your homepage and in the archive.

You can save drafts, edit later, delete, preview. The first time you write a new review this way, you'll realise you never want to go back.

### What needs to happen

There are two sides to this. Some of it I'll build for you (the config files and the build script). Some of it you'll click through in the Netlify dashboard (the auth stuff). I can't do the Netlify UI bits for you, but they're short.

### E1. I'll build these (when you're ready)

1. **An `admin` folder** at the top of your site with two files: `index.html` and `config.yml`. The `config.yml` defines the form you'll see, the fields, and where the data gets saved.
2. **A `reviews-data` folder** that will hold one JSON file per review. This becomes the new source of truth for new reviews.
3. **An updated build script** that Netlify runs every time you save something in the CMS. It turns each JSON file into the correct HTML review page, updates the archive, and updates the homepage.
4. **A `netlify.toml` file** at the top of the site telling Netlify how to run the build.

Once these are in, every "publish" click in the CMS triggers an automatic site rebuild.

### E2. You'll do these (in Netlify's dashboard)

These are one-time clicks once I've pushed the CMS files.

1. **Turn on Netlify Identity** (this is what lets you log in)
   - In your Netlify site dashboard, go to "Site configuration" → "Identity"
   - Click "Enable Identity"

2. **Restrict signups** (so random people can't make accounts on your admin)
   - Under Identity, click "Settings and usage"
   - Under "Registration preferences", set it to "Invite only"

3. **Turn on Git Gateway** (this is what lets Decap commit to GitHub on your behalf)
   - Still in Identity settings, scroll to "Services"
   - Click "Enable Git Gateway"

4. **Invite yourself**
   - Back on the Identity main page, click "Invite users"
   - Type `me@sasenka.com`
   - Click Send

5. **Accept your invitation**
   - Check your email, click the link, set a password
   - You're now the admin

6. **Test the admin page**
   - Go to `https://sasenkalovesfood.com/admin`
   - Log in with the email and password you just set
   - You should see the CMS dashboard with the form for writing a new review

### What this costs

Still zero. Netlify Identity is free for up to 1,000 users, and you only need one.

### When to do it

Best to do Parts A to D first, prove the full loop works, then come back for Part E. That way if anything goes wrong with the CMS we know the underlying pipeline is fine.

When you're ready, tell me, and I'll build the files in E1. Then you do the clicks in E2 (it takes about 5 minutes), and you're writing reviews from a browser.

---

## Going forward

Your everyday workflow before the CMS:

1. Make changes to files on your computer
2. Open GitHub Desktop, commit, push
3. Site updates within a minute

Your everyday workflow after the CMS:

1. Go to `sasenkalovesfood.com/admin`
2. Write the review, upload photos, click publish
3. Site updates within a minute
