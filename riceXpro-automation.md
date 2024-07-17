## Example of RiceXPro automation script
I searched expression patterns of ~200 top hit genes manually against data from [RiceXPro](https://ricexpro.dna.affrc.go.jp/RXP_4001/). Rather than navigate the site individually for each gene, I wrote a python script that automates the search. In brief, the script uses chromedriver to navigate to the site, find and enter gene info in the search box, then follow links to expression data (if any exist); then it grabs the two expression plots available and plots them to the screen. It's written in such a way that if you use a for loop to iterate over multiple genes, it won't proceed until the plots are closed to ensure that you've had a chance to get the information you're looking for.

Here's a screenshot video showing the script iterating over two genes:
![ricexpro-py-example](https://github.com/user-attachments/assets/32427c5f-be15-48d3-a9fc-30bf211aa7a8)






