| Build | Suite match | Corpus match | Suite silent-wrong | Corpus silent-wrong | Suite, corpus-weighted match | Suite, corpus-weighted silent |
|---|---|---|---|---|---|---|
| cf-computer-workerd-071b2b2 | 68.7% | 83.3% | 16.2% | 8.5% | 71.2% | 14.3% |
| jb-main-7a2a7a57 | 72.1% | 89.6% | 13.4% | 3.7% | 74.2% | 12.2% |
| jb-npm-3.6.0 | 70.7% | 88.6% | 14.8% | 4.7% | 72.7% | 13.7% |

Corpus build for each suite subject: cf-computer-workerd-071b2b2 = cf-computer-b681446f, jb-main-7a2a7a57 = jb-main-7a2a7a57, jb-npm-3.6.0 = jb-npm-3.6.0.

Rank agreement across the 3 builds: Spearman 1.00 (match), 1.00 (silent-wrong). Pearson 0.96 (match), 0.95 (silent-wrong).
Per family and build (45 points): Pearson 0.56 / Spearman 0.40 for the non-match rate; Pearson 0.36 / Spearman 0.41 for the silent-wrong rate.

| Pair | Match change, suite | Match change, corpus | Silent change, suite | Silent change, corpus | Families: same direction / opposite / no change |
|---|---|---|---|---|---|
| cf-computer-workerd-071b2b2 vs jb-main-7a2a7a57 | +3.4 pp | +6.30 pp | -2.8 pp | -4.75 pp | 7 / 1 / 7 |
| cf-computer-workerd-071b2b2 vs jb-npm-3.6.0 | +2.0 pp | +5.34 pp | -1.4 pp | -3.79 pp | 6 / 1 / 8 |
| jb-main-7a2a7a57 vs jb-npm-3.6.0 | -1.4 pp | -0.96 pp | +1.4 pp | +0.96 pp | 3 / 0 / 12 |

| Family | Corpus instances | Suite cases | cf-computer-workerd-071b2b2 non-match suite / corpus | jb-main-7a2a7a57 non-match suite / corpus | jb-npm-3.6.0 non-match suite / corpus |
|---|---|---|---|---|---|
| awk | 156 | 13 | 38.5% / 21.8% | 38.5% / 18.6% | 38.5% / 18.6% |
| checksum | 161 | 9 | 44.4% / 86.3% | 44.4% / 85.1% | 44.4% / 85.1% |
| cut-tr | 876 | 21 | 23.8% / 16.6% | 23.8% / 13.9% | 23.8% / 14.4% |
| diff-bytes | 46 | 18 | 83.3% / 84.8% | 77.8% / 65.2% | 77.8% / 65.2% |
| fileops | 885 | 24 | 37.5% / 53.7% | 33.3% / 6.0% | 33.3% / 6.0% |
| find-xargs | 74 | 12 | 25.0% / 58.1% | 25.0% / 56.8% | 25.0% / 56.8% |
| grep | 2614 | 44 | 43.2% / 12.1% | 29.5% / 8.0% | 38.6% / 10.8% |
| jq | 28 | 9 | 22.2% / 32.1% | 22.2% / 32.1% | 22.2% / 32.1% |
| ls-stat | 1158 | 35 | 60.0% / 60.5% | 48.6% / 54.3% | 48.6% / 54.6% |
| rg | 1239 | 23 | 17.4% / 31.5% | 13.0% / 26.2% | 17.4% / 31.1% |
| sed | 4841 | 43 | 25.6% / 6.2% | 25.6% / 5.1% | 25.6% / 5.8% |
| shell | 3336 | 88 | 28.4% / 15.8% | 29.5% / 10.8% | 29.5% / 11.5% |
| sort-uniq | 80 | 30 | 33.3% / 66.2% | 33.3% / 65.0% | 33.3% / 66.2% |
| view | 9057 | 100 | 23.0% / 16.8% | 21.0% / 9.1% | 22.0% / 10.2% |
| wc | 567 | 20 | 30.0% / 35.6% | 25.0% / 30.0% | 25.0% / 30.7% |
