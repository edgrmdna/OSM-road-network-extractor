# 🚀 Quick Start Guide - Deploy in 10 Minutes

## Option 1: Test Locally First (Recommended)

1. **Install dependencies:**
```bash
pip install streamlit osmnx geopandas folium streamlit-folium
```

2. **Run the app:**
```bash
streamlit run osm_extractor_app.py
```

3. **Open browser:** http://localhost:8501

4. **Test it out:**
   - Try "El Segundo, California, USA" as a place name
   - Choose "Drive" network type
   - Select "GeoJSON" format
   - Click "Extract Network"

---

## Option 2: Deploy to Streamlit Cloud (FREE!)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository (e.g., "osm-road-extractor")
3. Make it public
4. Don't initialize with README (we already have one)

### Step 2: Upload Files to GitHub

**Option A: Using GitHub Web Interface**
1. Click "uploading an existing file"
2. Drag and drop all 4 files:
   - `osm_extractor_app.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`
3. Commit changes

**Option B: Using Git Command Line**
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git push -u origin main
```

### Step 3: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **"New app"**
4. Fill in:
   - **Repository:** your-username/osm-road-extractor
   - **Branch:** main
   - **Main file path:** osm_extractor_app.py
5. Click **"Deploy!"**

### Step 4: Wait for Deployment

- Takes 2-5 minutes
- You'll see build logs
- When done, your app URL: `https://your-app-name.streamlit.app`

### Step 5: Share Your App! 🎉

Your app is now live and publicly accessible!

---

## Customization Ideas

Want to enhance your app? Here are some ideas:

1. **Add more network filters:**
   - Filter by road type (highway, residential, etc.)
   - Filter by speed limits
   - Include/exclude bridges/tunnels

2. **Add batch processing:**
   - Upload multiple polygons at once
   - Process multiple cities from a list

3. **Add analytics:**
   - Network connectivity metrics
   - Road type distribution charts
   - Length statistics by road class

4. **Add authentication:**
   - Use Streamlit secrets for API keys
   - Add user accounts

5. **Add more export options:**
   - KML for Google Earth
   - CSV of attributes only
   - Graph format for network analysis

---

## Troubleshooting

**Build fails on Streamlit Cloud:**
- Check that `requirements.txt` is in the root directory
- Verify all package names are spelled correctly
- Check the build logs for specific errors

**App is slow:**
- OSMnx downloads can take time for large areas
- Consider adding caching for repeated queries
- Add progress bars for better UX

**Out of memory errors:**
- Limit the size of extractable areas
- Add file size checks
- Consider upgrading to Streamlit Cloud paid tier

---

## Next Steps

1. ✅ Test locally
2. ✅ Deploy to Streamlit Cloud
3. 📢 Share with your colleagues
4. 🔧 Customize based on feedback
5. 🌟 Star the repo!

---

## Support

Questions? Issues?
- Check the main README.md
- Review Streamlit docs: https://docs.streamlit.io
- Review OSMnx docs: https://osmnx.readthedocs.io

Happy mapping! 🗺️
