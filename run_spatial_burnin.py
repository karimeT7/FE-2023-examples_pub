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

# Addining the numbers of sweepinp
sim_start_year=2000
sim_years=30
serialize_years = 30
burnin_years=30
num_seeds=5
phase = 'burnin'
tag = 'spatial_sim'

if(phase=="burnin"):
    num_seeds = 1         # number stochastic realizations
    # Vary Habitat Scale Factors
    num_xTLH_samples = 10
    min_xTLH = 0
    max_xTLH = 1

def set_param_fn(config):
    """
    This function is a callback that is passed to emod-api.config to set config parameters, including the malaria defaults.
    """
    import emodpy_malaria.malaria_config as conf
    
    # The next four conf is made for the purpose of adding climate data in the modele. 
    config = conf.set_team_defaults(config, manifest)
    climate_root = os.path.join('climate','FE_EXAMPLE', '2019001-2019365')
    
    config.parameters.Air_Temperature_Filename = os.path.join(climate_root,
        'dtk_15arcmin_air_temperature_daily.bin')
    config.parameters.Land_Temperature_Filename = os.path.join(climate_root,
        'dtk_15arcmin_air_temperature_daily.bin')
    config.parameters.Rainfall_Filename = os.path.join(climate_root,
        'dtk_15arcmin_rainfall_daily.bin')
    config.parameters.Relative_Humidity_Filename = os.path.join(climate_root, 
        'dtk_15arcmin_relative_humidity_daily.bin')
    
    #Addind information about the types of mosquito 
    conf.add_species(config, manifest, ["gambiae", "arabiensis", "funestus"])
  
    config.parameters.Simulation_Duration = sim_years*365 #Adding the numbers of values to be generated 
    #config.parameters.Run_Number = 0 #The number of time each values must be generated randomly
    
    config.parameters.Serialized_Population_Writing_Type = "TIMESTEP"
    config.parameters.Serialization_Time_Steps = [365 * burnin_years]
    config.parameters.Serialization_Mask_Node_Write = 0
    config.parameters.Serialization_Precision = "REDUCED"
    config.parameters.Simulation_Duration = burnin_years*365
    #config.parameters.x_Temporary_Larval_Habitat= np.logspace= 0.681292 
    return config
 



def update_serialize_parameters(simulation, df, x: int):
    # Serialized file path:
    path = df["serialized_file_path"][x]    
    # Other parameters from burnin that need to be carried over:
    xTLH = df["x_Temporary_Larval_Habitat"][x]
    
    simulation.task.set_parameter("Serialized_Population_Filenames", df["Serialized_Population_Filenames"][x])  # Set serialized population filename
    simulation.task.set_parameter("Serialized_Population_Path", os.path.join(path, "output"))                   # Set serialized population path
    simulation.task.set_parameter("x_Temporary_Larval_Habitat", xTLH)          
    return {"xTLH":xTLH}      # Return serialized parameters as tags


  
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

def build_demog():
    """
    This function builds a demographics input file for the DTK using emod_api.
    """
    #Change the population to 500
    # NOTE: The id_ref used to generate climate and demographics must match! ID climate :da6dfa3f-6526-ee11-aa08-b88303911bc1
    demog = Demographics.from_csv(input_file = os.path.join(manifest.input_dir,"demographics","nodes.csv"), 
                                                        id_ref="FE_EXAMPLE", 
                                                        init_prev = 0.01, 
                                                        include_biting_heterogeneity = True)
    
    demog.SetEquilibriumVitalDynamics()

    age_distribution = Distributions.AgeDistribution_SSAfrica
    demog.SetAgeDistribution(age_distribution)
    return demog


def build_camp(cm_cov_u5=0.8):
    """
    This function builds a campaign input file for the DTK using emod_api.
    """
    camp.set_schema(manifest.schema_file)
    
    return camp


def general_sim(selected_platform):
    """
    This function is designed to be a parameterized version of the sequence of things we do 
    every time we run an emod experiment. 
    """
    

    platform = Platform(selected_platform, job_directory=manifest.job_directory, partition='b1139', time='6:00:00',
                        account='b1139', modules=['singularity'], max_running_jobs=100)
    # Task #
    ########
    # create EMODTask #
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
    
    # set the singularity image to be used when running this experiment #
    task.set_sif(manifest.SIF_PATH, platform)
    # add weather directory as an asset #
    task.common_assets.add_directory(os.path.join(manifest.input_dir, "climate"), relative_path="climate")
    # Builder #
    ########### 
    # add builder #
    builder = SimulationBuilder() 
    ### Parameters to sweep over in burnin ###
    # Run number
    builder.add_sweep_definition(partial(set_param, param='Run_Number'), range(num_seeds))
    # x_Temporary_Larval_Habitat
    builder.add_sweep_definition(partial(set_param, param='x_Temporary_Larval_Habitat'), np.logspace(min_xTLH, max_xTLH, num_xTLH_samples))

    # add weather directory as an asset
    task.common_assets.add_directory(os.path.join(manifest.input_dir,
        "climate", "FE_EXAMPLE","2019001-2019365"), relative_path="climate")
    # create experiment from builder
    user = os.getlogin()
    
    #**********************A modifier
    experiment = Experiment.from_builder(builder, task, name=f'{user}_{tag}_{phase}')
    
    # The last step is to call run() on the ExperimentManager to run the simulations.
    experiment.run(wait_until_done=True, platform=platform)


    # Check result
    if not experiment.succeeded:
        print(f"Experiment {experiment.uid} failed.\n")
        exit()

    print(f"Experiment {experiment.uid} succeeded.")



if __name__ == "__main__":
    import emod_malaria.bootstrap as dtk
    import pathlib

    dtk.setup(pathlib.Path(manifest.eradication_path).parent)

    selected_platform = "SLURM_LOCAL"
    general_sim(selected_platform)



