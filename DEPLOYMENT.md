# Deployment

## Official URLs

- Frontend (official): [https://swing-analyser-kappa.vercel.app](https://swing-analyser-kappa.vercel.app)
- Backend API (official): [https://swing-analyser-production.up.railway.app](https://swing-analyser-production.up.railway.app)
- GitHub repository: [https://github.com/diyaromar2001-lgtm/swing-analyser](https://github.com/diyaromar2001-lgtm/swing-analyser)
- Branch used for production: `main`

## Official Vercel project

The official Vercel deployment for the current app is the project that serves:

- `swing-analyser-kappa.vercel.app`

This is the frontend that includes the current Actions UI updates, including:

- Edge `24m / 36m` toggle in Advanced View
- current Actions/Crypto switcher
- latest deployment-linked UI fixes

## Old Vercel URL

This older frontend should not be treated as production:

- `frontend-seven-snowy-63.vercel.app`

It serves an outdated UI and can confuse users because it does not necessarily match the latest backend or current production frontend.

## Recommended action for the old Vercel URL

Preferred action:

1. Open the old Vercel project that owns `frontend-seven-snowy-63.vercel.app`
2. Go to `Settings`
3. Remove the custom/public domain if one is attached
4. Archive or delete the old project if it is no longer needed

If you want to keep the old project temporarily:

1. Update that project to deploy the same GitHub repo and `main` branch
2. Or add a redirect in that project so all traffic goes to:
   - `https://swing-analyser-kappa.vercel.app`

## Notes

- The frontend uses Vercel rewrites to proxy `/api/*` to Railway.
- Production decisions for the Actions Command Center remain based on the default `24m` edge horizon.
- The `36m` edge horizon is for Advanced View analysis only.
