# Mining Public Health Discourse from News and Social Media

**Group 4 | Text as Big Data | University of Ibadan**

## Project overview

This project examines vaccination-related public discourse using a corpus of 429,803 documents collected from Twitter, Reddit and online news sources, covering 2020–2025.

The analysis investigates three research questions:

1. What are the dominant themes in vaccination discourse, and how have they changed over time?
2. How does sentiment vary across time, sources and major public-health events?
3. How accurately can a sparse, high-dimensional classifier predict thematic labels, and which terms contribute to its predictions?

The analysis uses R, Quarto, lexicon-based sentiment analysis, Latent Dirichlet Allocation (LDA) and multinomial lasso regression.

## Requirements

Install the following software before proceeding:

- R
- RStudio
- Quarto
- Git

An internet connection is required for the initial installation of R packages.

## Reproducing the analysis

### Step 1: Download the project

Clone this repository using Git:

```bash
git clone <REPOSITORY_URL>
cd public-health-text-mining
```

Alternatively, download the repository as a ZIP file from GitHub and extract it.

### Step 2: Open the RStudio project

Open the `.Rproj` file in the repository root.

This establishes the working directory used by the project and its relative file paths.

### Step 3: Restore the R package environment

Open the RStudio Console and run:

```r
install.packages("renv")
renv::restore()
```

The `renv.lock` file records the package versions used by the project.

Allow the installation process to finish before proceeding.

### Step 4: Confirm the processed datasets

The `data/processed/` directory contains the processed datasets used by the analysis.

These allow group members to reproduce the analytical workflow without repeating the original data collection process.

Check the available files:

```r
list.files("data/processed", recursive = TRUE)
```

The raw data acquisition notebook or script is provided for documentation and optional independent data collection. It is not required for the standard reproduction workflow.

### Step 5: Run the notebooks in order

Open the Quarto (`.qmd`) notebooks in RStudio.

**Notebook 1: Data preparation**

Use the provided processed datasets to inspect the cleaned corpus and prepare the inputs required for analysis. The original data acquisition stage can be skipped.

**Notebook 2: Exploratory analysis and topic modelling**

Run the notebook containing:

- Corpus composition and document counts
- Term frequencies by source
- Sentiment distributions and trends
- LDA topic modelling
- Topic prevalence over time
- Word co-occurrence network
- Sentiment around major public-health events

**Notebook 3: Classification**

Run the notebook containing:

- Sparse document-term matrix and topic-label preparation
- Stratified training and testing split
- Ten-fold cross-validation
- Multinomial lasso classification
- Held-out performance evaluation
- Analysis of influential classification terms

**Important:** Run notebooks in the documented order. Each notebook must load or reconstruct the objects it requires. Objects from an earlier RStudio session should not be assumed to exist.

### Step 6: Render the notebooks

Open each `.qmd` file in RStudio and click **Render**.

Alternatively, use the terminal:

```bash
quarto render notebooks/<NOTEBOOK_NAME>.qmd --to html
```

Replace `<NOTEBOOK_NAME>` with the actual filename.

Rendered notebooks contain the code, output, visualisations and accompanying interpretations.

### Step 7: Verify the main results

The following values provide reference points for checking successful reproduction:

| Output | Expected result |
|---|---:|
| Cleaned combined corpus | 429,803 documents |
| LDA modelling sample | 11,080 documents |
| LDA vocabulary | 6,614 terms |
| Number of LDA topics | 5 |
| Classifier training set | 8,876 documents |
| Classifier testing set | 2,204 documents |
| Held-out classification accuracy | 63.57% |
| Macro-F1 | 0.5963 |
| Majority-class baseline accuracy | 37.21% |

Random seeds are used in the modelling workflow to improve reproducibility. Minor numerical differences may occur across R versions, platforms or computational environments.

## Data sources and acquisition

The research combines three publicly accessible data sources.

**Reddit: Arctic Shift**

Archived Reddit comments from the `r/vaccines` community were obtained using Arctic Shift, covering the study period from 2020 to 2025.

Website: https://arctic-shift.photon-reddit.com/

**Twitter: Kaggle**

A publicly archived vaccination-related Twitter dataset was obtained from Kaggle. The available Twitter data primarily cover August 2020 to September 2022.

Website: https://www.kaggle.com/

The exact dataset title, URL and version should be recorded in the project data-source documentation.

**Online news: Media Cloud**

Media Cloud was used to identify vaccination-related news coverage across the study period. Article text was subsequently obtained from accessible source pages and cleaned for analysis.

Website: https://www.mediacloud.org/

The news collection represents a selected sample rather than a complete archive of vaccination coverage.

### Optional independent data collection

Group members wishing to reconstruct the corpus from its original sources may consult the data acquisition scripts and source documentation.

Independent collection may produce different results because public archives, website accessibility, source coverage and data availability can change.

The recommended reproduction route is therefore to use the processed datasets supplied with this repository.

## Methodological limitations

The combined corpus is not representative of all public discourse about vaccination. Source volumes, collection methods and date coverage differ substantially.

Lexicon-based sentiment scores measure recognised positive and negative language, not necessarily support for or opposition to vaccination.

The five topic labels were derived from an unsupervised LDA model. The corpus was split before vocabulary construction and LDA estimation, and test-topic proportions were inferred using the frozen training model. The lasso classifier was evaluated against these generated labels, not independently annotated ground truth. Consequently, its reported accuracy measures out-of-sample agreement with the topic model.

Language metadata were unavailable for the Twitter and Reddit archives. English-language tokenisation and sentiment resources were applied to those sources without claiming that every social-media document was independently verified as English. This may contribute to unclassified sentiment and noisy topic vocabulary.

## Ethical considerations

The analysis focuses on aggregate patterns rather than individual users. Publicly accessible text may still contain sensitive information, and redistribution must comply with applicable licensing, copyright and platform conditions.

The results should not be used to infer individual medical conditions, identify vaccine supporters or opponents, or make decisions about individuals.

## Outputs

Generated figures are stored in `outputs/figures/`, and tabular results may be stored in `outputs/tables/`.

These include sentiment trends, topic distributions, word co-occurrence networks, classifier evaluation and influential-term visualisations.
