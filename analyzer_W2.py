import os
import datetime
import pandas as pd
import numpy as np
import sys
import re
import random
from idmtools.entities import IAnalyzer	
from idmtools.entities.simulation import Simulation
import manifest

## For plotting
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.dates as mdates


class InsetChartAnalyzer(IAnalyzer):

    @classmethod
    def monthparser(self, x):
        if x == 0:
            return 12
        else:
            return datetime.datetime.strptime(str(x), '%j').month

    def __init__(self, expt_name, sweep_variables=None, channels=None, working_dir=".", start_year=0):
        super(InsetChartAnalyzer, self).__init__(working_dir=working_dir, filenames=["output/InsetChart.json"])
        self.sweep_variables = sweep_variables or ["Run_Number"]
        self.inset_channels = channels or ['Statistical Population', 'New Clinical Cases', 'Blood Smear Parasite Prevalence',
                                           'Infectious Vectors']
        self.expt_name = expt_name
        self.start_year = start_year

    def map(self, data, simulation: Simulation):
        simdata = pd.DataFrame({x: data[self.filenames[0]]['Channels'][x]['Data'] for x in self.inset_channels})
        simdata['Time'] = simdata.index
        simdata['Day'] = simdata['Time'] % 365
        simdata['Year'] = simdata['Time'].apply(lambda x: int(x / 365) + self.start_year)
        simdata['date'] = simdata.apply(
            lambda x: datetime.date(int(x['Year']), 1, 1) + datetime.timedelta(int(x['Day']) - 1), axis=1)

        for sweep_var in self.sweep_variables:
            if sweep_var in simulation.tags.keys():
                simdata[sweep_var] = simulation.tags[sweep_var]
            elif sweep_var == 'Run_Number' :
                simdata[sweep_var] = 0
        return simdata

    def reduce(self, all_data):

        selected = [data for sim, data in all_data.items()]
        if len(selected) == 0:
            print("No data have been returned... Exiting...")
            return

        if not os.path.exists(os.path.join(self.working_dir, self.expt_name)):
            os.mkdir(os.path.join(self.working_dir, self.expt_name))

        adf = pd.concat(selected).reset_index(drop=True)
        adf.to_csv(os.path.join(self.working_dir, self.expt_name, 'All_Age_InsetChart.csv'), index=False)

class MonthlyPfPRAnalyzer(IAnalyzer):

    def __init__(self, expt_name, sweep_variables=None, working_dir='./', start_year=0,
                 burnin=None, filter_exists=False):

        super(MonthlyPfPRAnalyzer, self).__init__(working_dir=working_dir,
                                                   filenames=["output/MalariaSummaryReport_monthly.json"]
                                                   )
     
        self.sweep_variables = sweep_variables or ["Run_Number"]
        self.expt_name = expt_name
        self.start_year = start_year
        self.burnin = burnin
        self.filter_exists = filter_exists

    def filter(self, simulation: Simulation):
        if self.filter_exists:
            file = os.path.join(simulation.get_path(), self.filenames[0])
            return os.path.exists(file)
        else:
            return True

    def map(self, data, simulation: Simulation):
        adf = pd.DataFrame()
        fname = self.filenames[0]
        age_bins = data[self.filenames[0]]['Metadata']['Age Bins']
      
        for age in range(len(age_bins)):
            d = data[fname]['DataByTimeAndAgeBins']['PfPR by Age Bin'][:-1]
            pfpr = [x[age] for x in d]
          
            d = data[fname]['DataByTimeAndAgeBins']['Annual Clinical Incidence by Age Bin'][:-1]
            clinical_cases = [x[age] for x in d]
         
            d = data[fname]['DataByTimeAndAgeBins']['Annual Severe Incidence by Age Bin'][:-1]
            severe_cases = [x[age] for x in d]

            d = data[fname]['DataByTimeAndAgeBins']['New Infections by Age Bin'][:-1]
            new_infections = [x[age] for x in d]

            d = data[fname]['DataByTimeAndAgeBins']['Annual Mild Anemia by Age Bin'][:-1]
            mild_anemia = [x[age] for x in d]

            d = data[fname]['DataByTimeAndAgeBins']['Pf Gametocyte Prevalence by Age Bin'][:-1]
            gamete_prev = [x[age] for x in d]
            
            d = data[fname]['DataByTimeAndAgeBins']['Mean Log Parasite Density by Age Bin'][:-1]
            dens = [x[age] for x in d]            

            d = data[fname]['DataByTimeAndAgeBins']['Average Population by Age Bin'][:-1]
            pop = [x[age] for x in d]

            simdata = pd.DataFrame({'month': range(1, len(pfpr)+1),
                                    'PfPR': pfpr,
                                    'Cases': clinical_cases,
                                    'Severe_cases': severe_cases,
                                    'New_infections': new_infections,
                                    'Anemia': mild_anemia,
                                    'Mean_density': dens,
                                    'Gametocyte_prevalence': gamete_prev,
                                    'Pop': pop})
                       
            simdata['agebin'] = age_bins[age]


            adf = pd.concat([adf, simdata])

        for sweep_var in self.sweep_variables:
            if sweep_var in simulation.tags.keys():
                try:
                    adf[sweep_var] = simulation.tags[sweep_var]
                except:
                    adf[sweep_var] = '-'.join([str(x) for x in simulation.tags[sweep_var]])
        
        adf['Year'] = None
        adf['Year'] = np.floor((adf['month']-1)/12)+self.start_year
        
        return adf

    def reduce(self, all_data):

        selected = [data for sim, data in all_data.items()]
        print(len(selected))
        if len(selected) == 0:
            print("\nWarning: No data have been returned... Exiting...")
            return

        if not os.path.exists(os.path.join(self.working_dir, self.expt_name)):
            os.mkdir(os.path.join(self.working_dir, self.expt_name))

        print(f'\nSaving outputs to: {os.path.join(self.working_dir, self.expt_name)}')

        adf = pd.concat(selected).reset_index(drop=True)
        adf.to_csv((os.path.join(self.working_dir, self.expt_name, 'PfPR_ClinicalIncidence_monthly.csv')),
                   index=False)
        
if __name__ == "__main__":

    from idmtools.analysis.analyze_manager import AnalyzeManager
    from idmtools.core import ItemType
    from idmtools.core.platform_factory import Platform

    
    expts = {
        #'week2_weather' : '2c090358-cb7b-44e5-a2fd-842a6c23a5b7'
        'week3_out_sweep' : 'cd818ae0-f1fc-4824-9028-cbc75b905ec3'
    }
    

    jdir = manifest.job_directory
    wdir = os.path.join(jdir, 'my_outputs')
    
    if not os.path.exists(wdir):
        os.mkdir(wdir)
    
    sweep_variables = ['Run_Number'] 

    # set desired InsetChart channels to analyze and plot
    channels_inset_chart = ['Statistical Population', 'True Prevalence', 'New Clinical Cases','Infectious Vectors','Rainfall','Air Temperature']

    
    with Platform('SLURM_LOCAL',job_directory=jdir) as platform:

        for expt_name, exp_id in expts.items():
          
            analyzer = [InsetChartAnalyzer(expt_name=expt_name,
                                      channels=channels_inset_chart,
                                      sweep_variables=sweep_variables,
                                      start_year = 2023,
                                      working_dir=wdir),
                        MonthlyPfPRAnalyzer(expt_name=expt_name,
                                      sweep_variables=sweep_variables,
                                      start_year=2023,
                                      working_dir=wdir)]
            
            # Create AnalyzerManager with required parameters
            manager = AnalyzeManager(configuration={}, ids=[(exp_id, ItemType.EXPERIMENT)],
                                     analyzers=analyzer, partial_analyze_ok=True)
            # Run analyze
            manager.analyze()
            
            
 
    # read in analyzed InsetChart data
    expt_name=list(expts.keys())[0]
    df = pd.read_csv(os.path.join(wdir, expt_name, 'All_Age_InsetChart.csv'))
    df['date'] = pd.to_datetime(df['date'])
    df = df.groupby(['date'] + sweep_variables)[channels_inset_chart].agg(np.mean).reset_index()

    # make InsetChart plot
    fig1 = plt.figure('InsetChart', figsize=(12, 6))
    fig1.subplots_adjust(hspace=0.5, left=0.08, right=0.97)
    fig1.suptitle(f'Analyzer: InsetChartAnalyzer')
    axes = [fig1.add_subplot(2, 3, x + 1) for x in range(6)]
    for ch, channel in enumerate(channels_inset_chart):
        ax = axes[ch]
        for p, pdf in df.groupby(sweep_variables):
            ax.plot(pdf['date'], pdf[channel], '-', linewidth=0.8, label=p)
        ax.set_title(channel)
        ax.set_ylabel(channel)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    if len(sweep_variables) > 0:
        axes[-1].legend(title=sweep_variables)
    fig1.savefig(os.path.join(wdir, expt_name, 'InsetChart.png'))
    
