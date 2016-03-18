
df <- read.csv("refine.csv", 
                header = TRUE,  
                fill = TRUE, 
                col.names= c("company", "Product_code_number", "address", "city","country","name"), 
                strip.white = TRUE, 
                stringsAsFactors=TRUE)
library(plyr)
library(dplyr)
library(tidyr)
df$company <- revalue(df$company, c("phillps"="phillips","Phillips"="phillips",
                                    "AKZO"="akzo", "akz0"="akzo","ak zo"="akzo","Akzo"="akzo","philips"="phillips","phillipS"="phillips",
                                    "phllips"="phillips","fillips"="phillips","phlips"="phillips","Phillips"="phillips",
                                    "Van Houten"="van houten","van Houten"="van houten", "Uniliver"="unilever","Unilever"="unilever",
                                    "unilver"="unilever")) 
df <- separate(df,Product_code_number, c("product_code", "product_number"), sep = "-")
df$productcategory <- mapvalues(df$product_code, from = c("p","x","v","q"), to = c("Smartphone","Laptop","TV","Tablet"))
df$company_philips <- mapvalues(df$company, from = c("phillips","akzo","van houten","unilever"), to = c(1,0,0,0))
df$company_akzo <- mapvalues(df$company, from = c("phillips","akzo","van houten","unilever"), to = c(0,1,0,0))
df$company_vanhouten <- mapvalues(df$company, from = c("phillips","akzo","van houten","unilever"), to = c(0,0,1,0))
df$company_unilever <- mapvalues(df$company, from = c("phillips","akzo","van houten","unilever"), to = c(0,0,0,1))

df$product_smartphone <- mapvalues(df$product_code, from = c("p","x","v","q"), to = c(1,0,0,0))
df$product_tv <- mapvalues(df$product_code, from = c("p","x","v","q"), to = c(0,0,1,0))
df$product_laptop <- mapvalues(df$product_code, from = c("p","x","v","q"), to = c(0,1,0,0))
df$product_tablet <- mapvalues(df$product_code, from = c("p","x","v","q"), to = c(0,0,0,1))

df <- mutate(df,full_address= address,city,country)
df