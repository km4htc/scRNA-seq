Using scRNA-seq to identify markers of rice root cell differentiation
================

Here, I’ll work through the pre-processing and then analaysis of a
publicly available dataset of 10x Genomics scRNA-seq data from rice
roots. These data were prepared by the Wang Lab at the Institute of
Plant Physiology and Ecology and downloaded from the NCBI bioproject
[PRJNA706435](https://www.ncbi.nlm.nih.gov/bioproject?LinkName=sra_bioproject&from_uid=13362410)
and SRA run
[SRR13853440](https://trace.ncbi.nlm.nih.gov/Traces/?view=run_browser&acc=SRR13853440&display=metadata).

``` r
library(DropletUtils)
library(tidyverse)
library(ggpointdensity)
library(scico)
library(scales)
library(irlba)
library(Matrix)
library(Seurat)
library(tibble)
library(patchwork)

# These funcs are copied from a kallisto/bustools tutorial made by 
# the Patcher Lab (https://www.kallistobus.tools/tutorials/)
get_knee_df <- function(mat) {
  total <- rank <- NULL
  tibble(total = Matrix::colSums(mat), # total reads per droplet
         rank = row_number(dplyr::desc(total))) %>% # ranks droplets in desc order by total
    distinct() %>%
    dplyr::filter(total > 0) %>% 
    arrange(rank)
}

get_inflection <- function(df, lower = 100) {
  log_total <- log_rank <- total <-  NULL
  df_fit <- df %>% 
    dplyr::filter(total > lower) %>% 
    transmute(log_total = log10(total),
              log_rank = log10(rank))
  d1n <- diff(df_fit$log_total)/diff(df_fit$log_rank)
  right.edge <- which.min(d1n)
  10^(df_fit$log_total[right.edge])
}

knee_plot <- function(df, inflection) {
  total <- rank_cutoff <- NULL
  annot <- tibble(inflection = inflection,
                  rank_cutoff = max(df$rank[df$total > inflection]))
  ggplot(df, aes(total, rank)) +
    geom_path() +
    geom_vline(aes(xintercept = inflection), data = annot, linetype = 2, 
               color = "gray40") +
    geom_hline(aes(yintercept = rank_cutoff), data = annot, linetype = 2, 
               color = "gray40") +
    geom_text(aes(inflection, rank_cutoff, 
                  label = paste(rank_cutoff, "'cells'")),
              data = annot, vjust = 1) +
    scale_x_log10() +
    scale_y_log10() +
    labs(y = "Rank", x = "Total UMIs") +
    annotation_logticks()
}
```

We’ll start by loading the cell x gene count matrix that’s output from
Kallisto/ Bustools. These files are in the repository along with the
steps used to make them.

``` r
# load output from kallisto/bustools
# matrix where rows are genes, cols are cells
res_mat <- ReadMtx(mtx="data/kb-output/cells_x_genes.mtx",
                   cells="data/kb-output/cells_x_genes.barcodes.txt",
                   features="data/kb-output/cells_x_genes.genes.txt",
                   feature.column = 1,
                   mtx.transpose = TRUE)

# Read in genes and gene names
tr2g <- read_tsv("data/kb-output/t2g.txt", col_names = c("transcript", "gene", "gene_name",
                                          "drop", "chromosome", "start", "stop", "strand"))
tr2g <- distinct(tr2g[, c("gene", "gene_name", "chromosome")])
```

``` r
# Inspect library saturation
# Empty/near-empty droplets will have ~0 reads and ~0 observed genes  
lib_sat <- tibble(nCount = colSums(res_mat), # total reads per droplet
                  nGene = colSums(res_mat > 0)) # total number of genes observed in a droplet
ggplot(lib_sat, aes(nCount, nGene)) +
  geom_bin2d(bins = 50) +
  scale_fill_distiller(palette = "Blues", direction = 1) +
  scale_x_log10() + scale_y_log10() + annotation_logticks()
```

<img src="scRNAseq-rice_files/figure-gfm/filter empty droplets-1.png" width="50%" style="display: block; margin: auto;" />

``` r
# It seems like the data from the SRA accession may be pre-filtered for quality
# Normally you would expect to see high density around 0,0
```

Another way to assess library saturation is with a knee plot. On the
y-axis is droplet/cell rank, determined by the total number of reads in
a droplet (x-axis). The inflection point of the curve indicates a
reasonable threshold for filtering droplets/cells by total read count.

``` r
knee_df <- get_knee_df(res_mat)
inflection <- get_inflection(knee_df)
# again, based on the shape of the curve this data seems to be pre-filtered
knee_plot(knee_df, inflection)
```

<img src="scRNAseq-rice_files/figure-gfm/knee plot-1.png" width="50%" style="display: block; margin: auto;" />

``` r
# Filter out low readcount cells (likely empty or lower-quality droplets)
res_mat <- res_mat[, colSums(res_mat) > 500]
res_mat <- res_mat[Matrix::rowSums(res_mat) > 0,]
```

We also want to filter out droplets with a high percentage of reads
mapped to either the mitochondria or chloroplast. Droplets where these
reads are more abundant may indicate droplets in which the nuclear
transcripts of lysed cells are more likely to have been lost/degraded,
but organellar reads persisted because they were protected by an
additional membrane layer.

``` r
# get a list of genes from organellar genomes
mt <- filter(tr2g, chromosome=="Mt")$gene %>%
  intersect(., rownames(res_mat))
pt <- filter(tr2g, chromosome=="Pt")$gene %>%
  intersect(., rownames(res_mat))

# create Seurat obj and calculate percent reads mitochondrial/chloroplast per cell
seu <- CreateSeuratObject(res_mat)
seu[["percent.mt"]] <- PercentageFeatureSet(seu, features=mt)
seu[["percent.pt"]] <- PercentageFeatureSet(seu, features=pt)

# this plot looks OK
# would look worse if low readcount cells hadn't already been filtered above
p.mt <- ggplot(seu@meta.data, aes(nCount_RNA, percent.mt)) +
  geom_pointdensity() +
  scale_color_scico(palette = "batlowW", direction = 1, end = 0.9) +
  labs(x = "Total read count", y = "Percentage mitochondrial") +
  theme_bw()
p.pt <- ggplot(seu@meta.data, aes(nCount_RNA, percent.pt)) +
  geom_pointdensity() +
  scale_color_scico(palette = "batlowW", direction = 1, end = 0.9) +
  labs(x = "Total read count", y = "Percentage chloroplast") +
  theme_bw()
p.mt | p.pt
```

<img src="scRNAseq-rice_files/figure-gfm/filter by percent organellar reads-1.png" width="75%" style="display: block; margin: auto;" />

``` r
# Remove cells with > 10% mitochondrial reads or 1.25% chloroplast
seu <- subset(seu, subset = percent.mt < 10 & percent.pt < 1.25)
```

With the matrix now filtered, we normalize the read counts to reduce
skew in read count distribution and stabilize variance across genes.
There are plenty of ways to normalize, but here we use the Seurat
default which is log normalization. Once normalized, we can look for
genes with high variation in expression from cell to cell.

``` r
# Normalize data
seu <- NormalizeData(seu)
# identify a subset of genes that exhibit high cell-to-cell variation
seu <- FindVariableFeatures(seu)
```

In RunPCA(), we use these variable features (rather than all \>30K
genes) as the basis for dimension reduction. We can also visualize the
dimension loadings to see which genes explain the most variance on a
given axis and make an elbow plot to show which axes explain the most
variance across the dataset.

``` r
# run PCA
seu <- ScaleData(seu)
seu <- RunPCA(seu)

# visualize the dim loadings
p1 <- VizDimLoadings(seu, dims = 1:2, reduction = "pca") +
  theme(axis.text = element_text(size=6))
p2 <- ElbowPlot(seu) + theme(axis.title.y = element_text(size=10))
(p1 | p2) + plot_layout(design="AAB") & theme(axis.text = element_text(size=9))
```

<img src="scRNAseq-rice_files/figure-gfm/dimension reduction-1.png" width="90%" style="display: block; margin: auto;" />

UMAP is a useful way of visualizing the dimension reduction done via
PCA. Here, we use the first 15 axes of the PCA results to run UMAP
(another dimension-reducing method) to visually represent those 15 axes
in just 3 (or the number of n.components).

``` r
# run other dimension-reduction algorithms
seu <- RunUMAP(seu, dims = 1:15, n.neighbors = 100,  
               n.components = 3, n.epochs = 500)
DimPlot(seu, reduction = "umap", dims = c(1,2)) + 
  theme(legend.position = "none") +
  labs(x = "UMAP 1", y = "UMAP 2")
```

<img src="scRNAseq-rice_files/figure-gfm/run UMAP-1.png" width="75%" style="display: block; margin: auto;" />

We can then use these data to identify neighbors and clusters,
i.e. cells that are closer together in the reduced-dimension space and
therefore have similar overall gene expression patterns——and therefore
indicate different cell types, treatments, etc.

``` r
seu <- FindNeighbors(seu, reduction="umap", dims=1:3, 
                     n.trees = 500, k.param=100)
seu <- FindClusters(seu, resolution = 0.7, n.start=100, n.iter=1000)
```

    ## Modularity Optimizer version 1.3.0 by Ludo Waltman and Nees Jan van Eck
    ## 
    ## Number of nodes: 15711
    ## Number of edges: 1825821
    ## 
    ## Running Louvain algorithm...
    ## Maximum modularity in 100 random starts: 0.9104
    ## Number of communities: 20
    ## Elapsed time: 43 seconds

``` r
DimPlot(seu, reduction = "umap", dims=c(1,2)) +
  labs(x = "UMAP 1", y = "UMAP 2")
```

<img src="scRNAseq-rice_files/figure-gfm/cluster cells and find marker genes-1.png" width="75%" style="display: block; margin: auto;" />

``` r
# Can plot in 3D with plotly; helps to differentiate between clusters
# p <- DimPlot(seu, reduction = "umap", dims=c(1,3))
# g <- ggplot_build(p)
# pal <- unique(g$data[[1]]["colour"])
# pal <- as.vector(pal$colour)
# temp <- seu@reductions[["umap"]]@cell.embeddings %>% as.data.frame()
# temp$cluster <- seu@meta.data[["seurat_clusters"]]
# temp$cluster <- as.factor(temp$cluster)
# plotly::plot_ly(temp, x = ~umap_1, y = ~umap_2, z = ~umap_3, color = ~cluster, size = 0.5, alpha=1, colors = pal)
```

With clusters identified, we can look for genes whose expression
uniquely identify a given cluster. Below, we run several different tests
to identify such marker genes.

``` r
# find markers for every cluster compared to all remaining cells, 
# report only the positive ones
markers <- FindAllMarkers(seu, test.use = "wilcox_limma", only.pos = TRUE, 
                          min.pct = 0.5, logfc.threshold = 1) %>% 
  filter(p_val_adj < 0.05) %>%
  arrange(cluster, desc(avg_log2FC))

markers.negbinom <- FindAllMarkers(seu, test.use = "negbinom", 
                                   only.pos = TRUE, min.pct = 0.5) %>% 
  filter(p_val_adj < 0.05) %>%
  arrange(cluster, desc(avg_log2FC))

markers.roc <- FindAllMarkers(seu, test.use = "roc",
                              only.pos = TRUE, min.pct = 0.5) %>% 
  arrange(cluster, desc(power))

# look for markers that are common to all lists
common_markers <- function(cluster, num_hits=10, print_hits=TRUE){
  wilcox <- filter(markers, cluster == {{cluster}})$gene[1:num_hits]
  negbin <- filter(markers.negbinom, cluster == {{cluster}})$gene[1:num_hits]
  roc <- filter(markers.roc, cluster == {{cluster}})$gene[1:num_hits]
  common <- intersect(wilcox, negbin) %>%
    intersect(., roc)
  print(paste0(length(common), " common markers found for cluster ",cluster))
  if (print_hits){
    cat(common, sep="\n")
  }
}
# for (i in 0:19){
#   common_markers(i, 10)
# }
# turns out both wilcox and negbinom produced identical results; roc was a bit different
#common_markers(cluster=14, num_hits=20)

# Let's plot the top marker for cluster 10
p1 <- FeaturePlot(seu, features = "Os05g0135500")
p2 <- DimPlot(seu, reduction="umap") + 
  scale_color_manual(values=c(rep( "lightgray", 10), "red", rep("lightgray",9)))
p1 | p2
```

<img src="scRNAseq-rice_files/figure-gfm/find marker genes-1.png" width="75%" style="display: block; margin: auto;" />

Not all identified markers are equally helpful, and not all clusters had
clear marker genes identified. Below is a function to visualize the top
10 markers per cluster to compare markers; but, it’s also helpful to
compare one method of FindAllMarkers() against another.

``` r
# plot expression of top10 marker genes per cluster
plot_func <- function(cluster, numclusts=19){
  vals <- rep("lightgray", numclusts+1)
  vals[cluster + 1] <- "red"
  p1 <- DimPlot(seu, reduction = "umap", alpha = 0.5, dims=c(1,2)) &
    scale_color_manual(values = vals) &
    theme(legend.position = "none")
  
  m <- filter(markers, cluster=={{cluster}}) %>% .[1:10,] %>% 
    arrange(p_val_adj) %>% .$gene
  p2 <- FeaturePlot(seu, ncol = 5, dims = c(1,2), features = m) &
    theme(legend.position = "none",
          axis.title = element_blank(),
          plot.title = element_text(size=8))
  p <- (p1 | p2) + 
    patchwork::plot_layout(design="ABBB")
  tit <- paste0("Cluster ",{{cluster}})
  p <- p + plot_annotation(title = tit) &
    theme(plot.title = element_text(hjust=0.5, face="bold"))
  return(p)
}
cl <- list()
for (cluster in 0:19){
  name = paste0("cl",cluster)
  cl[[name]] <- plot_func(cluster=cluster)
}
cl[["cl10"]]
```

<img src="scRNAseq-rice_files/figure-gfm/plot top markers per cluster-1.png" width="95%" style="display: block; margin: auto;" />

Next I used marker genes to try to identify the cell type of each
cluster. The results are below, but to get them I used the RiceXPro
dataset 4001 to investigate the tissue and developmental stage-specific
expression pattern for each gene. This became too tedious so I wrote a
python script to automate the searches using google chrome’s webdriver;
the script is available in the repository as well as a screen recording
showing how it works.

``` r
# Function to print the names of the top N marker genes per cluster
print_markers <- function(cluster, num_markers=10){
  filter(markers, cluster=={{cluster}}) %>%
  .[1:num_markers,] %>%
  arrange(p_val_adj) %>%
  .$gene %>%
  cat(sep="\n")
}

# # Cluster 0####
# cl[["cl0"]]
# print_markers(cluster=0, num_markers=10)
# # Os06g0216000 - elong/mat I, and all; lean end
# # Os11g0210201 - no hits
# # Os01g0952900 - low uniform exp; lean epi
# # Os02g0777800 - elong-mat V; lean end
# # Os02g0740600 - elong-mat V; epi and end
# # Os06g0192800 - elong-mat II; epi and end
# # Os02g0193300 - root cap, low uniform exp; unclear
# # Os06g0215500 - low uniform; unclear
# # Os06g0133500 - norm dist ~mat I; lean epi
# # Os10g0525800 - low uniform; unclear
# #####
# 
# # Cluster 1####
# cl[["cl1"]]
# print_markers(cluster=1, num_markers=10)
# # Os02g0285700 - no hits
# # Os05g0463000 - elongation, some mat I; unclear
# # Os03g0831400 - elongation, some mat I; unclear
# # Os04g0555700 - elongation, some mat I; leans epi
# # Os10g0578200 - elongation/mat I; unclear
# # Os06g0335900 - low uniform exp, higher in mat; leans end in mat V
# # Os06g0135900 - elongation, some mat I; unclear
# # Os07g0484200 - elongation, some mat I; unclear
# # Os05g0372900 - elongation, some mat I; leans epi
# # Os04g0674800 - elongation/maturation I; epi
# #####
# 
# # Cluster 2####
# cl[["cl2"]]
# print_markers(cluster=2, num_markers=10)
# # Os03g0195800 - elong/mat I, norm dist around; unclear
# # Os06g0490400 - low uniform; unclear
# # Os03g0428700 - elongation; unclear
# # Os03g0830200 - elongation; leans epi
# # Os09g0409100 - elongation/mat I, come mat II-V; epi
# # Os07g0531400 - low uniform; unclear
# # Os10g0370800 - root cap, elong/mat I; end
# # Os01g0868600 - root cap-elongation; unclear
# # Os03g0155900 - elongation; unclear
# # Os02g0112600 - maturation I, low norm dist around; unclear
# #####
# 
# # Cluster 3####
# cl[["cl3"]]
# print_markers(cluster=3, num_markers=10)
# # Os06g0681600 - elongation; end
# # Os01g0263300 - elongation/mat I, some mat II; end
# # Os06g0538900 - elongation, low uniform otherwise; end
# # Os03g0102500 - division/elongation; unclear
# # Os05g0499300
# # Os06g0143100
# # Os02g0653200
# # Os03g0121200
# # Os10g0493600 - elongation/mat I, some mat II; end
# # Os03g0121300 - division, some root cap; unclear
# #####
# 
# # Cluster 4####
# cl[["cl4"]]
# print_markers(cluster=4, num_markers=10)
# # Os10g0454200 - root cap/division; end
# # Os06g0514800 - root cap/division; leans cortex
# # Os02g0554900 - root cap/division, low otherwise; leans end
# # Os03g0699800 - root cap/division, some elong-mat II; unclear
# # Os07g0616600 - division; end
# # Os05g0584200 - root cap/mat V, low inbetween; end
# # Os02g0814700 - division; end
# # Os06g0266400 - no hits
# # Os04g0473400 - division; end
# # Os05g0138200 - root cap/division, low otherwise; unclear
# #####
# 
# # Cluster 5####
# cl[["cl5"]]
# print_markers(cluster=5, num_markers=10)
# # Os01g0914100 - uniformish high; end
# # Os01g0914300 - division; leans end
# # Os12g0114800 - elongation; cortex
# # Os11g0115100 - elongation; cortex
# # Os01g0127600 - division, some root cap; unclear
# # Os04g0554600 - elongation, low otherwise; leans end, leans epi in mat V
# # Os04g0554500 - elongation; leans cortex
# # Os10g0552700 - elongation, decrease to mat V; cortex
# # Os11g0643800 - division, low otherwise; unclear
# # Os03g0385400 - norm dist ~elongation; cortex and end
# #####
# 
# # Cluster 6####
# cl[["cl6"]]
# print_markers(cluster=6, num_markers=10)
# # Os01g0838350 - no hits
# # Os07g0139600 - division, low otherwise; end
# # Os02g0503400 - division, some root cap, low otherwise; end
# # Os07g0608700 - division, low otherwise; end
# # Os02g0478700 - division, low otherwise; end
# # Os10g0564300 - division, low otherwise; end
# # Os02g0478600 - division, low otherwise; end
# # Os04g0613600 - division, low otherwise; end
# # Os03g0818400 - division, low otherwise; end
# # Os01g0834500 - division, low otherwise; end
# #####
# 
# # Cluster 7####
# cl[["cl7"]]
# print_markers(cluster=7, num_markers=10)
# # Os02g0666200 - elong/mat I, decrease to mat V; increase to end
# # Os04g0233400 - elong, decrease to mat V; increase to end
# # Os02g0658100 - elong, decrease to mat V; increase to end
# # Os10g0552700 - elong, decrease to mat V; cortex
# # Os10g0552300 - elong; unclear
# # Os07g0676900 - elong decrease to mat II; cortex and end
# # Os02g0629200 - elong, decrease to mat V; increase to end
# # Os04g0554500 - elong; leans cortex
# # Os03g0111200 - elong, decrease to mat V, some root cap; end, some epi
# # Os10g0552600 - elong-mat II, decrease to mat V; cortex
# #####
# 
# # Cluster 8####
# cl[["cl8"]]
# print_markers(cluster=8, num_markers=10)
# # Os03g0121300 - division, some root cap; unclear
# # Os05g0556900 - division, low otherwise; end
# # Os08g0129200 - division, low otherwise; end
# # Os02g0489400 - division, low otherwise; end
# # Os02g0103700 - division, low otherwise; end
# # Os01g0127600 - division, some root cap; unclear
# # Os07g0616600 - division, low otherwise; end
# # Os01g0191100 - division, low otherwise; end
# # Os09g0501200 - no hits
# # Os07g0180900 - division, low otherwise; end
# #####
# 
# # Cluster 9####
# cl[["cl9"]]
# print_markers(cluster=9, num_markers=10)
# # Os03g0103200 - elong-mat V; cortex
# # Os03g0103100 - mat I-V; cortex
# # Os06g0547400 - elong-mat II, some mat III-IV; cortex/end
# # Os10g0137300 - unclear
# # Os11g0167800 - elong-mat II, some mat III-IV; leans epi, end in mat V
# # Os05g0247100 - mat I-II, some elong/mat III, less mat IV-V; leans epi
# # Os12g0548700 - norm dist ~mat I; cortex
# # Os06g0336200 - elongation/mat I, decrease to mat V; leans cortex
# # Os12g0548401 - no hits
# # Os12g0548501 - no hits
# #####
# 
# # Cluster 10####
# cl[["cl10"]]
# print_markers(cluster=10, num_markers=10)
# # Os05g0135500 - norm dist elong-mat II, some mat V; epi, end in mat V
# # Os03g0416200 - elong/mat I; epi
# # Os08g0489300 - norm dist elong-mat II, some mat V; epi, end in mat V
# # Os09g0422500 - norm dist ~mat I; leans epi (low exp)
# # Os01g0750300 - norm dist elong-mat II, some mat III-V; leans epi, end in mat V
# # Os07g0636800 - elong decrease to mat II; leans epi
# # Os07g0204400 - norm dist elong-mat II, some mat III-V;unclear, end in mat V
# # Os03g0819600 - norm dist ~mat I; leans epi
# # Os03g0401300 - norm dist ~mat I; end
# # Os05g0134400 - elongation/mat I, decrease to mat V; leans epi
# #####
# 
# # Cluster 11####
# cl[["cl11"]]
# print_markers(cluster=11, num_markers=10)
# # Os06g0180100 - no hits
# # Os03g0155500 - no hits
# # Os04g0494600 - low uniform; unclear
# # Os07g0639000 - division, some elongation; unclear
# # Os10g0454200 - root cap, some division; leans end
# # Os01g0868600 - root cap-elong; unclear
# # Os02g0554900 - root cap/division; leans end (low exp)
# # Os02g0112600 - normal dist ~mat I; unclear
# # Os03g0734300 - root cap; increase to epi
# # Os03g0699800 - root cap decrease to mat II; unclear
# #####
# 
# # Cluster 12####
# cl[["cl12"]]
# print_markers(cluster=12, num_markers=10)
# # Os04g0228400 - division/elong; unclear (low exp)
# # Os11g0539200 - elong, some division; unclear
# # Os01g0611000 - norm dist ~division, some root cap, dec to mat IV; end
# # Os07g0568700 - root cap/division, some elong; leans end
# # Os10g0556100 - norm dist ~ mat I/II; increase to end
# # Os05g0477600 - division, some elong; leans end (low exp)
# # Os10g0536700 - division/elong decrease to mat V; end
# # Os01g0309100 - root cap decrease to mat V; increase to end
# # Os03g0121300 - division, some root cap; unclear (low exp)
# # Os02g0138000 - division, some root cap/elong dec to mat V; end
# #####
# 
# # Cluster 13####
# cl[["cl13"]]
# print_markers(cluster=13, num_markers=10)
# # Os06g0681600 - elong; end
# # Os06g0649000 - low uniform; unclear
# # Os08g0138200 - low uniform; unclear
# # Os01g0185900 - elong/mat I, low otherwise; epi
# # Os02g0671100 - low uniform; unclear
# # Os08g0173600 - elong/mat I; epi
# # Os05g0439400 - norm dist ~elong; leans end
# # Os03g0437200 - low uniform; unclear
# # Os03g0187800 - norm dist ~elong; increase to epi
# # Os08g0277200 - low uniform; unclear
# #####
# 
# # Cluster 14####
# cl[["cl14"]]
# print_markers(cluster=14, num_markers=10)
# # Os01g0248900 - elong; increase to end
# # Os08g0120600 - elong/mat I, low mat II-V; unclear
# # Os01g0956200 - elong/mat I dec to mat V; cortex
# # Os11g0186900 - root cap and elong, low mat I-V; increase to epi
# # Os11g0147150 - no hits
# # Os01g0292200 - norm dist ~mat I; leans epi/cortex
# # Os03g0155900 - elong; unclear
# # Os12g0567800 - elong/mat I decrease to mat V; epi and end
# # Os10g0490900 - root cap, some elong, mat I dec to mat V; decrease to end
# # Os12g0571100 - mat I,IV-V, some elong/mat II-III; epi
# #####
# 
# # Cluster 15####
# cl[["cl15"]]
# print_markers(cluster=15, num_markers=10)
# # Os02g0188400 - root cap; unclear (low exp)
# # Os12g0112000 - elong/mat I, low mat II-V; end
# # Os01g0948600 - elong slight inc to mat V; end
# # Os05g0186300 - root cap dec to mat V, no division; end
# # Os11g0112400 - norm dist ~elong; leans end (low exp)
# # Os04g0615200 - norm dist ~mat I; end
# # Os04g0450000 - lean elong-mat V; unclear
# # Os02g0695600 - norm dist ~mat I; end
# # Os12g0603800 - low uniform; unclear
# # Os07g0549900 - division, low otherwise; end
# #####
# 
# # Cluster 16####
# cl[["cl16"]]
# print_markers(cluster=16, num_markers=10)
# # Os03g0368900 - norm dist ~mat I from elong to mat IV; end
# # Os02g0653200 - elong dec to mat V; end
# # Os06g0143100 - elong dec to mat V; end
# # Os01g0291500 - elong/mat I dec to mat V; epi and end
# # Os08g0157500 - elong/mat I dec to mat V; epi and end, leans end
# # Os02g0187800 - elong/mat I dec to mat V; epi and end, leans end
# # Os01g0358100 - elong dec to mat V; leans epi
# # Os12g0548700 - norm dist ~mat I; cortex
# # Os01g0143900 - elong/mat I dec to mat V; epi and end
# # Os11g0704500 - mat I, some elong, less mat I-V; increase to epi
# #####
# 
# # Cluster 17####
# cl[["cl17"]]
# print_markers(cluster=17, num_markers=10)
# # Os10g0546100 - elong/mat I; epi
# # Os03g0608000 - elong/mat I; epi
# # Os07g0499500 - elong/mat I; epi
# # Os03g0288000 - mat I, some elong, low mat II-V; epi
# # Os04g0674800 - elong/mat I; epi
# # Os01g0164075 - no hits
# # Os07g0638600 - elong, some mat I; leans epi (low exp)
# # Os01g0294500 - no hits
# # Os04g0472200 - elong/mat I; epi
# # Os10g0122600 - elong/mat I low mat II-V; end
# #####
# 
# # Cluster 18####
# cl[["cl18"]]
# print_markers(cluster=18, num_markers=10)
# # Os05g0507000 - division; increase to end
# # Os03g0128300 - division; increase to end
# # Os01g0896400 - division; increase to end
# # Os04g0496300 - division; increase to end
# # Os03g0736500 - no hits
# # Os01g0756900 - division; end
# # Os01g0273100 - division; end
# # Os02g0258200 - division; increase to end
# # Os03g0780200 - division dec to mat V, some root cap; increase to end
# # Os03g0146300 - division, low otherwise; end
# #####
# 
# # Cluster 19####
# cl[["cl19"]]
# print_markers(cluster=19, num_markers=10)
# # Os07g0104100 - mat I, some elong and mat II and IV; end
# # Os01g0971400 - mat I, some elong and mat II and IV; end
# # Os07g0638500 - elong dec to mat II; end
# # Os02g0528100 - elong dec to mat IV, some root cap; end
# # Os01g0842500 - mat I, some elong and mat II and IV; end
# # Os03g0850900 - mat I, some elong and mat II-IV; end
# # Os08g0546700 - norm dist ~elong, small spike at mat IV; end
# # Os01g0134900 - elong/mat I dec to mat V; end
# # Os03g0178400 - norm dist ~mat I; end
# # Os01g0260800 - elong/mat I, low otherwise; end
# #####
```

I also used markers identified in the Nature paper from [Zhang et
al.2021](doi.org/10.1038/s41467-021-22352-4) to determine cluster cell
type. I added their supplemental data file to the repository, but you
should also check out the paper.

``` r
natpaper <- readxl::read_xlsx("data/zhang-2021-supp.xlsx", 
                              sheet = "Figure 1", skip = 1) %>%
  arrange(cluster.id, desc(pct.exp), desc(avg.exp)) %>%
  mutate(gene = str_sub(gene, 1, 12))

# Function to pick top markers from Zhang et al.
pick_markers <- function(cluster.id, num_markers=10){
  filter(natpaper, cluster.id=={{cluster.id}}) %>%
    .$gene %>% .[1:num_markers]
}
# FeaturePlot(end, features = pick_markers(cluster.id=15), ncol=5)
# DimPlot(end, reduction="umap", dims=c(1,2))

# These were less useful than hoped for, so let's try a different strategy
# Instead search for markers with high expression in ONE cluster only
# note that cluster.id 12 is xylem according to Zhang et al.
filter(natpaper, cluster.id == 12) %>% 
  select(c(gene, pct.exp)) %>%
  arrange(desc(pct.exp)) %>% .[1:10,]
```

    ## # A tibble: 10 × 2
    ##    gene         pct.exp
    ##    <chr>          <dbl>
    ##  1 Os10g0467800   82.7 
    ##  2 Os09g0422500   81.6 
    ##  3 Os02g0745100    9.62
    ##  4 Os04g0684300    7.59
    ##  5 Os02g0805200    6.20
    ##  6 Os07g0134000    5.45
    ##  7 Os04g0540900    5.02
    ##  8 Os12g0637100    4.38
    ##  9 Os02g0595900    3.74
    ## 10 Os08g0490900    3.21

``` r
p1 <- FeaturePlot(seu, dims=c(1,2), features ="Os10g0467800")
p2 <- DimPlot(seu, reduction="umap", dims=c(1,2)) + 
  scale_color_manual(values=c(rep( "lightgray", 10), "red", rep("lightgray",9)))
p1 | p2
```

<img src="scRNAseq-rice_files/figure-gfm/hand-picked markers-1.png" width="75%" style="display: block; margin: auto;" />

``` r
# Here are the more useful markers I found this way:
#meristem
ms <- c("Os03g0279200", "Os05g0438700", "Os08g0490900", "Os08g0512600")
#xylem
xy <- c("Os01g0971400", "Os03g0817800")
#meristem and endodermis
ms.and.endo <- c("Os02g0805200")
#endodermis
endo <- c("Os04g0684300")
#cortex
cor <- c("Os05g0231700", "Os02g0823100")
#exodermis + putative root cap junction
exo.and.rcj <- c("Os04g0452700")
#phloem
phl <- c("Os01g0236300", "Os09g0498800")
#protophloem
pphl <- c("Os04g0298700")
#epidermis + root hair
epi.and.rh <- c("Os02g0595900")
  #EMC + trichoblast
  emc.and.tb <- c("Os10g0122600")
  #trichoblast + atrichoblast
  tb.and.atb <- c("Os03g0150800")
#vascular cylinder
vc <- c("Os04g0540900")
#pericycle
pc <- c("Os10g0524300")

# A quick way to recreate the figures above with different genes, or lists of genes
# is to use the code below:
# get a palette where "cluster" is red and all other clusters are gray
# get_pal <- function(cluster, n_clusters){
#   vals <- rep("lightgray", n_clusters+1)
#   vals[cluster+1] <- "red"
#   return(vals)
# }
# dims = c(1,2)
# p1 <- DimPlot(seu, reduction="umap", dims=dims) +
#   scale_color_manual(values=get_pal(cluster=10, n_clusters=19))
# p2 <- FeaturePlot(seu, features = xy, ncol=length(xy), dims=dims) &
#   theme(legend.position = "none")
# (p1 | p2) + plot_layout(design="ABB")
```

In cases where it’s not clear which cluster a published/known marker
belongs to because of cluster overlap in two dimensions, it can be
helpful to plot a heatmap of average expression of a gene per cluster.
This makes it clearer which cluster has the highest expression of a
gene.

``` r
# Use this code to look at multiple genes at a time
scdata <- GetAssayData(seu, slot="counts", assay="RNA") %>%
  .[xy,] %>% CreateSeuratObject()
scdata <- NormalizeData(scdata)
scdata <- ScaleData(scdata)
scdata <- GetAssayData(scdata, slot="scale.data") %>% as.data.frame() %>% t()
sclusters <- seu@meta.data %>% as.data.frame() %>% select(seurat_clusters)
merge(scdata, sclusters, by="row.names") %>%
  select(-"Row.names") %>% as.data.frame() %>%
  group_by(seurat_clusters) %>% 
  summarise_all(.funs=list(mean=mean)) %>%
  column_to_rownames("seurat_clusters") %>%
  as.matrix() %>%
  pheatmap::pheatmap(scale = "none", cluster_rows = FALSE)
```

<img src="scRNAseq-rice_files/figure-gfm/unnamed-chunk-1-1.png" width="50%" style="display: block; margin: auto;" />

``` r
# Use this code to look at one gene at a time
# feat="Os01g0236300"
# scdata <- GetAssayData(seu, slot="counts", assay="RNA") %>%
#   .[feat,] %>% as.data.frame() 
# colnames(scdata) <- feat
# sclusters <- end@meta.data %>% as.data.frame() %>% select(seurat_clusters)
# merge(scdata, sclusters, by="row.names") %>%
#   select(-"Row.names") %>% as.data.frame() %>%
#   group_by(seurat_clusters) %>% 
#   summarise_all(.funs=list(val=mean)) %>%
#   column_to_rownames("seurat_clusters") %>%
#   as.matrix() %>%
#   pheatmap::pheatmap(scale = "none", cluster_rows = FALSE, cluster_cols = FALSE)
```

Through the two methods of identifying cluster cell type used above, it
became clear that UMAP 1 clearly separated endodermal and vascular cells
from epidermal ones, with the meristem/quiescent center sitting in
between.

``` r
# keep colors consistent for plots below
p <- DimPlot(seu, reduction = "umap", dims=c(1,2)) +
  farrowandball::scale_color_fb("spec", reverse=TRUE)
# ggplot_build(p) %>% .$data %>% .[[1]] %>% 
#   select(c(group, colour)) %>% distinct() %>% 
#   arrange(group) %>% 
#   mutate(val = paste0('"',group-1,'" = "',colour,'",')) %>%
#   .$val %>% cat(sep="\n")

pal <- c("0" = "#BF7A8F",
"1" = "#DC7E49",
"2" = "#C7546B",
"3" = "#B9485C",
"4" = "#447E86",
"5" = "#CE593E",
"6" = "#C3677D",
"7" = "#408278",
"8" = "#ECC363",
"9" = "#CEBD66",
"10" = "#599EC4",
"11" = "#E7AD5B",
"12" = "#51966A",
"13" = "#3E886B",
"14" = "#6EA66F",
"15" = "#5C83A2",
"16" = "#518094",
"17" = "#A83E4C",
"18" = "#5A90B3",
"19" = "#98B36E")

seu@reductions[["umap"]]@cell.embeddings %>%
  as.data.frame() %>%
  mutate(cluster = seu@meta.data[["seurat_clusters"]]) %>%
  mutate_at("cluster", factor, levels=c(0,6,2,3,17,5,1,11,8,9,19,
                                        14,12,13,7,4,16,15,18,10)) %>%
  ggplot(aes(x=umap_1, y=umap_2, color=cluster)) +
  geom_point(shape=19, size = 1, alpha = 1, stroke=0) + 
  scale_color_manual(values = pal) +
  theme_bw() +
  annotate("text", x=2, y=5.25, label="Meristem", size=5) +
  annotate("text", x=6, y=4, label="Epidermis", size=5) +
  annotate("text", x=-2.5, y=4.3, label="Endodermis", size=5) +
  annotate("text", x=-4.2, y=-4.7, label="Xylem", size=4) +
  annotate("text", x=3.9, y=-1.8, label="Trichoblast", size=4) +
  annotate("text", x=5, y=-3, label="Atrichoblast", size=4) +
  annotate('curve', x = 2.8, y = 4.2, 
           yend = 2.5, xend = 7, curvature=-0.15,
           linewidth = 1, 
           arrow = arrow(length = unit(0.5, 'cm'), type = "closed")) +
  annotate('curve', x = -1, y = 4, 
           yend = 3.5, xend = -4.5, curvature=0.05,
           linewidth = 1, 
           arrow = arrow(length = unit(0.5, 'cm'), type = "closed")) +
  labs(x = "UMAP 1", y = "UMAP 2")
```

<img src="scRNAseq-rice_files/figure-gfm/unnamed-chunk-2-1.png" width="75%" style="display: block; margin: auto;" />

If we take a closer look at the epidermis clusters (admittedly the less
convoluted of the two superclusters), we see that there are clear
trajectories towards trichoblast and atrichoblast cells, i.e. epidermal
root hair and non-root hair cells. Mature trichoblasts are in cluster
17, atrichoblasts in cluster 14.

``` r
# Epidermis = clusters 1,2,4,11,14,17
# Trichoblast = cluster 4 -> 1 -> 17
# Atrichoblast = cluster 11 -> 2 -> 14

# We can see that differentiation between trichoblast
# and atrichoblast cells starts early and that markers of 
# maturation should fall along UMAP 2
subset(seu, idents=c(1,2,4,11,14,17)) %>%
  DimPlot(., dims=c(2,3)) + 
  scale_color_manual(values=pal) +
  annotate("text", x=3, y=-1.2, label="to trichoblast", 
           size=5, angle=23) +
  annotate("text", x=3, y=2.5, label="to atrichoblast", 
           size=5, angle=-28) +
  annotate('curve', x = 3.8, y = 1.2, yend = 1.3, xend = -2.8,
           linewidth = 1, curvature = 0.35, 
           arrow = arrow(length = unit(0.5, 'cm'), type = "closed")) +
  annotate('curve', x = 3.8, y = -0.3, yend = -3.3, xend = -1,
           linewidth = 1, curvature = -0.05, 
           arrow = arrow(length = unit(0.5, 'cm'), type = "closed"))+
  labs(x = "UMAP 2", y = "UMAP 3")
```

<img src="scRNAseq-rice_files/figure-gfm/unnamed-chunk-3-1.png" width="75%" style="display: block; margin: auto;" />

Since these two trajectories begin near the meristem, it’s reasonable to
assume that they represent stages of differentiation for these two cell
types. And, because UMAP 2 clearly separates clusters along the
trajectory, we can use the loadings to identify genes that might play an
important role in trichoblast and atrichoblast cell differentiation.
Because we have a nice gradient, we can use simple linear regression of
gene expression along UMAP 2 to find genes that increase in expresion as
the cell types differentiate. Below, I’ve plotted the top hits for each
tricho- and atrichoblast.

``` r
# Let's look at trichoblasts only ####
trichoblast <- subset(seu, idents=c(1,4,17))
t.sd <- GetAssayData(trichoblast, slot="scale.data") %>% 
  as.data.frame() %>% t()
t.umap <- trichoblast@reductions[["umap"]]@cell.embeddings %>%
  as.data.frame()
t.cluster <- trichoblast@meta.data[["seurat_clusters"]]
# Merge scale data and umap loadings
trichoblast <- merge(t.sd, t.umap, by="row.names") %>%
  select(-"Row.names")
# Run regression for each gene against UMAP_2
runlm <- function(data, gene){
  x = data[,{{gene}}]
  y = data$umap_2
  out <- lm(x ~ y) %>%
    summary()
  adj.r.sq = out[["adj.r.squared"]]
  out <- out[["coefficients"]][2,] %>%
    as.data.frame()
  colnames(out) <- gene
  out <- t(out) %>% as.data.frame() %>%
    rownames_to_column("gene") %>%
    mutate(adj.r.sq = adj.r.sq)
  return(out)
}
genes = colnames(trichoblast)[1:(ncol(trichoblast)-3)]
lmdata = list()
for(gene in genes){
  lmdata[[gene]] <- runlm(trichoblast, gene)
}
lmdata <- bind_rows(lmdata) %>%
  `colnames<-`(c("gene", "est", "stderr", 
                 "t.value","p.value", "adj.r.sq"))
trichoblast$cluster <- t.cluster

# cross-reference top lm hits with markers
# doing so should help us limit the number of hits to genes that have higher
# expression in cluster 17 only (as identified in FindAllMarkers() above)
m <- filter(markers, cluster == 17)
lmdata %>%
  filter(p.value < 0.01 & gene %in% m$gene) %>%
  merge(., tr2g, by="gene", all.y=FALSE) %>%
  arrange(t.value) %>% .[1:10,1:7]
```

    ##            gene        est      stderr   t.value p.value  adj.r.sq gene_name
    ## 1  Os07g0499500 -0.6595696 0.010221794 -64.52581       0 0.6002642    prx102
    ## 2  Os06g0319133 -0.4212766 0.006937531 -60.72428       0 0.5707941      <NA>
    ## 3  Os07g0542900 -0.5557216 0.009188426 -60.48061       0 0.5688223   OsUCL22
    ## 4  Os10g0546100 -0.6709337 0.011160755 -60.11544       0 0.5658484      <NA>
    ## 5  Os03g0831400 -0.6315078 0.010515024 -60.05766       0 0.5653757      <NA>
    ## 6  Os04g0674800 -0.6727658 0.012333255 -54.54892       0 0.5176266   OsGH9C1
    ## 7  Os06g0335900 -0.6463205 0.012717053 -50.82314       0 0.4822554   OsXTH15
    ## 8  Os12g0163700 -0.5556239 0.010943123 -50.77380       0 0.4817702      <NA>
    ## 9  Os01g0294500 -0.6142061 0.012733122 -48.23688       0 0.4562357      <NA>
    ## 10 Os04g0472200 -0.5728420 0.012049751 -47.53973       0 0.4490190   OsFLA13

``` r
p.trich1 <- ggplot(trichoblast, aes(x=umap_2, y=Os07g0499500)) +
  geom_smooth(color="black") +
  theme_bw() +
  labs(y="Relative expression", x="UMAP 2", title="Os07g0499500") +
  theme(plot.title = element_text(hjust=0.5))

p.trich2 <- trichoblast %>%
  mutate_at("cluster", factor, levels = c(4,1,17)) %>%
  group_by(cluster) %>%
  ggplot(aes(x=cluster, y=Os07g0499500, fill=cluster)) +
  geom_boxplot() +
  labs(x="Cluster", y="Relative expression", fill="") +
  theme_bw() +
  scale_fill_manual(values = pal)

p.trich3 <- FeaturePlot(subset(seu, idents=c(1,2,4,11,14,17)), slot = "scale.data", 
            dims=c(2,3), features="Os07g0499500") +
  theme(plot.title = element_blank()) +
  labs(x="UMAP 2", y="UMAP 3")

p.trich <- (p.trich1 / p.trich2 / p.trich3) & 
  theme(axis.text = element_text(size=8),
        axis.title = element_text(size=10),
        panel.border = element_rect(linewidth = 0.5, color="black"),
        panel.grid = element_blank(),
        axis.line = element_blank(),
        legend.key.height = unit(0.5,"cm"),
        legend.text = element_text(size=8))


# now atrichoblasts ####
atrichoblast <- subset(seu, idents=c(2,11,14))
a.sd <- GetAssayData(atrichoblast, slot="scale.data") %>% 
  as.data.frame() %>% t()
a.umap <- atrichoblast@reductions[["umap"]]@cell.embeddings %>%
  as.data.frame()
a.cluster <- atrichoblast@meta.data[["seurat_clusters"]]
# Merge scale data and umap loadings
atrichoblast <- merge(a.sd, a.umap, by="row.names") %>%
  select(-"Row.names")

# Run regression for each gene against UMAP_2
genes = colnames(atrichoblast)[1:(ncol(atrichoblast)-3)]
a.lmdata = list()
for(gene in genes){
  a.lmdata[[gene]] <- runlm(atrichoblast, gene)
}
a.lmdata <- bind_rows(a.lmdata) %>%
  `colnames<-`(c("gene", "est", "stderr", 
                 "t.value","p.value", "adj.r.sq"))
atrichoblast$cluster <- a.cluster # add cluster ids back in

# cross-reference top lm hits with markers for atrichoblast
m <- filter(markers, cluster == 14)
a.lmdata %>%
  filter(p.value < 0.01 & gene %in% m$gene) %>%
  merge(., tr2g, by="gene", all.y=FALSE) %>%
  arrange(t.value) %>% .[1:10,1:7]
```

    ##            gene        est      stderr   t.value       p.value  adj.r.sq
    ## 1  Os07g0192000 -0.4164877 0.010616873 -39.22885 1.243046e-259 0.3942428
    ## 2  Os06g0319133 -0.3099815 0.008318321 -37.26491 1.783054e-239 0.3699799
    ## 3  Os11g0704500 -0.3928482 0.010707654 -36.68854 1.311397e-233 0.3627377
    ## 4  Os11g0186900 -0.5265974 0.016054124 -32.80138 8.785994e-195 0.3126679
    ## 5  Os12g0567800 -0.4488981 0.013741304 -32.66779 1.784234e-193 0.3109149
    ## 6  Os02g0740700 -0.3737000 0.011684199 -31.98337 8.302105e-187 0.3019070
    ## 7  Os05g0134700 -0.3024942 0.010281493 -29.42124 2.268295e-162 0.2678791
    ## 8  Os03g0155900 -0.5365684 0.018283186 -29.34764 1.107292e-161 0.2668968
    ## 9  Os11g0139700 -0.4300124 0.014695984 -29.26054 7.213591e-161 0.2657339
    ## 10 Os08g0120600 -0.4886210 0.016999581 -28.74312 4.672221e-156 0.2588218
    ##    gene_name
    ## 1       <NA>
    ## 2       <NA>
    ## 3       MT1A
    ## 4       ACO4
    ## 5     OsMT1f
    ## 6     OsMMP1
    ## 7      prx66
    ## 8   OsEXPA18
    ## 9       <NA>
    ## 10      <NA>

``` r
a.trich1 <- ggplot(atrichoblast, aes(x=umap_2, y=Os07g0192000)) +
  geom_smooth(color="black") +
  theme_bw() +
  labs(y="Relative expression", x="UMAP 2", title="Os07g0192000") +
  theme(plot.title = element_text(hjust=0.5))

a.trich2 <- atrichoblast %>%
  mutate_at("cluster", factor, levels = c(11,2,14)) %>%
  group_by(cluster) %>%
  ggplot(aes(x=cluster, y=Os07g0192000, fill=cluster)) +
  geom_boxplot() +
  labs(x="Cluster", y="Relative expression", fill="") +
  theme_bw() +
  scale_fill_manual(values = pal)

a.trich3 <- FeaturePlot(subset(seu, idents=c(1,2,4,11,14,17)), slot = "scale.data", 
            dims=c(2,3), features="Os07g0192000") +
  theme(plot.title = element_blank()) +
  labs(x="UMAP 2", y="UMAP 3")

a.trich <- (a.trich1 / a.trich2 / a.trich3) & 
  theme(axis.text = element_text(size=8),
        axis.title = element_text(size=10),
        panel.border = element_rect(linewidth = 0.5, color="black"),
        panel.grid = element_blank(),
        axis.line = element_blank(),
        legend.key.height = unit(0.5,"cm"),
        legend.text = element_text(size=8))

# plotted altogether
p.trich | a.trich
```

<img src="scRNAseq-rice_files/figure-gfm/unnamed-chunk-4-1.png" width="75%" style="display: block; margin: auto;" />

In the plot above we have the top hits tracking trichoblast and
atrichoblast cell differentiation in the left (Os07g0499500) and right
(Os07g0192000) columns, respectively. The top row shows transcript
expression levels along the UMAP 2 axis; recall that since more
meristem-like cells have higher UMAP 2 values and more differentiated
cells have lower UMAP 2 values, these plots indicate increasing
expression with developmental ‘time’. The middle row makes this clearer
with boxplots for each cluster, where left to right tracks with less to
more differentiated. Lastly, the bottom row highlights expression levels
for individual cells, allowing us to see the change in expression along
UMAP 2 as well as how specific expression is to a particular trajectory.

Looking into Os07g0499500 and Os07g0192000, you’ll find that they
correspond to a peroxidase, PRX102, and a AAA protein. Peroxidases,
which produce ROS species, are well known for their ability to influence
cell growth and elongation by controlling the pH of the apoplasm; acid
growth occurs when increased acidity activates expansin proteins
resulting in cell wall loosening ([Diaz-Tielas et
al. 2012](doi.org/10.4161/psb.21594)). Additionally, the ortholog for
PRX102 in Arabidopsis is specifically implicated in transcription
networks for root epidermal cell differentiation ([Bruex et
al. 2012](doi.org/10.1371/journal.pgen.1002446)). AAA proteins, on the
other hand, are ATPases Associated with diverse cellular Activities… not
exactly the kind of specificity you’d want in a good marker. But, maybe
looking farther down the list of top hits would reveal something more
useful!
