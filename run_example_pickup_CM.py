#Import the python module needed 
import pathlib
import os
from functools import partial 
import numpy as np
import manifest

#idmtools   
from idmtools.assets import Asset, AssetCollection  
from idmtools.builders import SimulationBuilder
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment
import emodpy_malaria.interventions.treatment_seeking as cm


#emodpy
from emodpy.emod_task import EMODTask
from emodpy.utils import EradicationBambooBuilds
from emodpy.bamboo import get_model_files
import emod_api.config.default_from_schema_no_validation as dfs
import emod_api.campaign as camp

#emodpy-malaria
import emodpy_malaria.demographics.MalariaDemographics as Demographics
import emod_api.demographics.PreDefinedDistributions as Distributions
from emodpy_malaria.reporters.builtin import *

from utils_slurm import build_burnin_df

serialize_years= 50 #This shouls match to burnin
sim_years=50
pickup_years=5
#Il faut remplacer dans la ligne suivante ton experiment ID obtenu en exécutant run-example_burnin.py
burnin_exp_id = "84f7102e-37db-4cdc-9615-56bddfe5a811" #change cet ID avec le sien ici
sim_start_year=2000
num_seeds=3


def set_param_fn(config):
    """
    This function is a callback that is passed to emod-api.config to set config parameters, including the malaria defaults.
    """
    import emodpy_malaria.malaria_config as conf
    config = conf.set_team_defaults(config, manifest)

    config.parameters.Air_Temperature_Filename = os.path.join('climate',
        'example_air_temperature_daily.bin')
    config.parameters.Land_Temperature_Filename = os.path.join('climate',
        'example_air_temperature_daily.bin')
    config.parameters.Rainfall_Filename = os.path.join('climate',
        'example_rainfall_daily.bin')
    config.parameters.Relative_Humidity_Filename = os.path.join('climate', 
        'example_relative_humidity_daily.bin')
    conf.add_species(config, manifest, ["gambiae", "arabiensis", "funestus"])

    config.parameters.Simulation_Duration = pickup_years*365
    #config.parameters.Run_Number = 3 #moved from 0 to 3
    config.parameters.x_Temporary_Larval_Habitat=0.681292
    #Add serialization - add pickup "read" parameters to config.json
    config.parameters.Serialized_Population_Reading_Type = "READ"
    config.parameters.Serialization_Mask_Node_Read = 0
    config.parameters.Serialization_Time_Steps = [serialize_years*365]
    return config



def set_param(simulation, param, value):
    """
    Set specific parameter value
    Args:
        simulation: idmtools Simulation
        param: parameter
        value: new value
    Returns:
        dict
    """
    return simulation.task.set_parameter(param, value)

### Function shipted, added  parameters to the function and case management
def build_camp(cm_cov_U5=0.80, cm_start = 1):

    camp.schema_path = manifest.schema_file

    # Add case management
    # This example assumes adults will seek treatment 75% as often as U5s and severe cases will seek treatment 15% more than U5s (up to 100% coverage)
    cm.add_treatment_seeking(camp, start_day=cm_start, drug=['Artemether', 'Lumefantrine'],
                      targets=[{'trigger': 'NewClinicalCase', 'coverage': cm_cov_U5, 
                                'agemin': 0, 'agemax': 5,
                                'seek': 1,'rate': 0.3},
                               {'trigger': 'NewClinicalCase', 'coverage': cm_cov_U5*0.75, 
                                'agemin': 5, 'agemax': 115,
                                'seek': 1,'rate': 0.3},
                               {'trigger': 'NewSevereCase', 'coverage': min(cm_cov_U5*1.15,1), 
                                'agemin': 0, 'agemax': 115,
                                'seek': 1,'rate': 0.5}],
                      broadcast_event_name="Received_Treatment")            
                     
    return camp



def build_demog():
    """
    This function builds a demographics input file for the DTK using emod_api.
    """
    #Change the population to 500
    demog = Demographics.from_template_node(lat=0.4479, lon=33.2026, pop=500, name="Example_Site")
    
    demog.SetEquilibriumVitalDynamics()

    age_distribution = Distributions.AgeDistribution_SSAfrica
    demog.SetAgeDistribution(age_distribution)
    return demog

def update_serialize_parameters(simulation, df, x: int):

   path = df["serialized_file_path"][x]
   seed = int(df["Run_Number"][x])

   simulation.task.set_parameter("Serialized_Population_Filenames", df["Serialized_Population_Filenames"][x])
   simulation.task.set_parameter("Serialized_Population_Path", os.path.join(path, "output"))
   simulation.task.set_parameter("Run_Number", seed) #match pickup simulation run number to burnin simulation

   return {"Run_Number":seed}

def general_sim(selected_platform):
    """
    This function is designed to be a parameterized version of the sequence of things we do 
    every time we run an emod experiment. 
    """

    # Set platform and associated values, such as the maximum number of jobs to run at one time
    platform = Platform(selected_platform, job_directory=manifest.job_directory, partition='b1139', time='2:00:00',
                            account='b1139', modules=['singularity'], max_running_jobs=10)

    # create EMODTask 
    print("Creating EMODTask (from files)...")

    
    task = EMODTask.from_default2(
        config_path="config.json",
        eradication_path=manifest.eradication_path,
        campaign_builder=build_camp,
        schema_path=manifest.schema_file,
        param_custom_cb=set_param_fn,
        ep4_custom_cb=None,
        demog_builder=build_demog,
        plugin_report=None
    )
    
    
    # set the singularity image to be used when running this experiment
    task.set_sif(manifest.SIF_PATH, platform)
   
    # Create simulation sweep with builder
    builder = SimulationBuilder()

    #builder.add_sweep_definition(partial(set_param, param='Run_Number'), range(num_seeds))
    #builder.add_sweep_definition(partial(set_param, param='x_Temporary_Larval_Habitat'), np.logspace(-0.5,1,10))
    # Create burnin df, retrieved from burnin ID (defined above)
    burnin_df = build_burnin_df(burnin_exp_id, platform, serialize_years*365)
    builder.add_sweep_definition(partial(update_serialize_parameters, df=burnin_df), range(len(burnin_df.index)))
    ## case management sweep 
    builder.add_multiple_parameter_sweep_definition(
        update_campaign_multiple_parameters,
        dict(
            cm_cov_U5=[0.0, 0.5, 0.95],
            cm_start=[1, 100, 365]
        )
    )
    #REPORTS
    add_event_recorder(task, event_list=["HappyBirthday", "Births","Received_Treatment"], #if needed
                       start_day=1, end_day=sim_years*365, 
                       node_ids=[1], min_age_years=0,
                       max_age_years=100)
    
  
    ####################################################
    for year in range(sim_years):
        start_day = 0 + 365 * year
        sim_year = sim_start_year + year
        add_malaria_summary_report(task, manifest, start_day=start_day,
                                   end_day=365+year*365, reporting_interval=30,
                                   age_bins=[0.25, 5, 115],
                                   max_number_reports=13,
                                   pretty_format=True, 
                                   filename_suffix=f'Monthly_U5_{sim_year}')
   
    # add weather directory as an asset
    task.common_assets.add_directory(os.path.join(manifest.input_dir,
        "example_weather", "out"), relative_path="climate")
    # create experiment from builder
    user = os.getlogin()
    
    experiment = Experiment.from_builder(builder, task, name="example_sim_pickup_CM")


    # The last step is to call run() on the ExperimentManager to run the simulations.
    experiment.run(wait_until_done=True, platform=platform)


    # Check result
    if not experiment.succeeded:
        print(f"Experiment {experiment.uid} failed.\n")
        exit()

    print(f"Experiment {experiment.uid} succeeded.")

 

##Second function added 

def update_campaign_multiple_parameters(simulation, cm_cov_U5, cm_start):

    build_campaign_partial = partial(build_camp, cm_cov_U5=cm_cov_U5, cm_start=cm_start)
    simulation.task.create_campaign_from_callback(build_campaign_partial)
  
    return dict(cm_cov_U5=cm_cov_U5, cm_start=cm_start)


    
    
if __name__ == "__main__":
    import emod_malaria.bootstrap as dtk
    import pathlib

    dtk.setup(pathlib.Path(manifest.eradication_path).parent)

    selected_platform = "SLURM_LOCAL"
    general_sim(selected_platform)
