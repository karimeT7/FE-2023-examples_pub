library(tidyverse) # import library 
library(readr)

#Load the dataset 
setwd("/projects/b1139/FE_fpx1364/FE-2023-examples/experiments/my_outputs/week3_out_pickup50")
f_list=list.files(pattern = "*\\.csv")

all_age <- read_csv(f_list[1])
all_age <- all_age %>% 
  rename_all(make.names)

col_name= colnames(all_age)

all_age %>%
  select(Statistical.Population, New.Clinical.Cases,Infected
         ,date)%>%
  group_by(date) %>%
  summarise_all(mean) %>%
  relocate(date) %>%
  gather(key="variable", value="value", -1) %>%
  ggplot(aes(x=date,y=value)) +
  facet_wrap(~variable, scales="free_y", ncol=3) +
  geom_path(aes(color=variable)) +
  ylab("") + xlab("") +
  theme_bw() +
  theme(axis.text.x = element_text(angle = 45, vjust=0.5),
        plot.margin = margin(0.4, 0.4,0.6, 0.6, "cm"))+
  guides(color="none")


PfPR <- read_csv(f_list[2])
PfPR <- PfPR %>% 
    rename_all(make.names)



col_name2= colnames(PfPR)

PfPR %>%
  select(month,PfPR,Cases,Severe_cases,New_infections,
         Anemia,Mean_density,Gametocyte_prevalence,agebin)%>%
  gather(key="variable", value="value", -c(1,9)) %>%
  ggplot(aes(x=month,y=value, color=as_factor(agebin))) +
  facet_wrap(~variable, scales="free_y", ncol=4) +
  geom_line() +
  ylab("") + xlab("") +
  theme_bw() +
  scale_x_continuous(breaks = seq(1,12, 2), labels=c("Jan", "Mar", "Mai", "Jul",
                                                     "Sep", "Nov"))+
  
  theme(axis.text.x = element_text(angle = 45, vjust=0.5))+
  guides(color="none")
