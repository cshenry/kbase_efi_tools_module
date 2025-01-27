
import io
import logging
import os
import subprocess
import uuid
import json
import shutil

# This is the SFA base package which provides the Core app class.
from base import Core
from installed_clients.DataFileUtilClient import DataFileUtil
from ..utils.utils import EfiUtils as utils

MODULE_DIR = "/kb/module"
TEMPLATES_DIR = os.path.join(MODULE_DIR, "lib/templates")


def get_streams(process):
    """
    Returns decoded stdout,stderr after loading the entire thing into memory
    """
    stdout, stderr = process.communicate()
    return (stdout.decode("utf-8", "ignore"), stderr.decode("utf-8", "ignore"))


class EstAnalysisJob:

    def __init__(self, config, shared_folder):
        #TODO: make this a config variable
        est_home = '/apps/EST'
        db_conf = config.get('efi_db_config')
        if db_conf != None:
            self.efi_db_config = db_conf
        else:
            self.efi_db_config = '/apps/EFIShared/db_conf.sh'

        est_conf = config.get('efi_est_config')
        if est_conf != None:
            self.efi_est_config = est_conf
        else:
            self.efi_est_config = '/apps/EST/env_conf.sh'

        #TODO:
        self.input_dataset_zip = config.get('input_dataset_zip')

        self.shared_folder = shared_folder
        self.output_dir = os.path.join(shared_folder, 'job_temp')
        utils.mkdir_p(self.output_dir)

        self.script_file = ''
        self.est_dir = est_home
        self.est_env = [self.efi_est_config, '/apps/EFIShared/env_conf.sh', '/apps/env.sh', '/apps/blast_legacy.sh', self.efi_db_config]

    def create_job(self, params):

        if self.input_dataset_zip == None:
            return None

        create_job_pl = os.path.join(self.est_dir, 'create_job.pl')

        # The input and output directories for the analysis job are the same, because we copy the transfer file in and unzip it.
        process_args = [create_job_pl, '--job-dir', self.output_dir]
        if params.get('job_id') != None:
            process_args.extend(['--job-id', params['job_id']])

        if params.get('ascore') == None:
            return None

        print(params)

        process_params = {'type': 'analysis'}
        process_params['a_job_dir'] = self.output_dir
        process_params['zip_transfer'] = self.input_dataset_zip
        process_params['filter'] = params.get('filter', "eval")
        process_params['minval'] = params.get('ascore')
        if params.get('minlen') != None:
            process_params['minlen'] = params['min_len']
        if params.get('maxlen') != None:
            process_params['maxlen'] = params['max_len']
        if params.get('uniref_version') != None:
            process_params['uniref_version'] = params['uniref_version']

        json_str = json.dumps(process_params)

        print("### JSON INPUT PARAMETERS TO create_job.pl ####################################################################\n")
        print(json_str + "\n\n\n\n")

        process_args.extend(['--params', "'"+json_str+"'"])
        process_args.extend(['--env-scripts', ','.join(self.est_env)])

        process = subprocess.Popen(
            process_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = get_streams(process)
        if stdout != None:
            script_file = stdout.strip()
        else:
            return None

        print("### OUTPUT FROM CREATE JOB ####################################################################################\n")
        print(str(stdout) + "\n---------\n")
        print("### ERR\n")
        print(str(stderr) + "\n\n\n\n")

        self.script_file = script_file

        return script_file

    def get_blast_params(self, params, process_params):
        if params.get('option_blast') != None:
            process_params['type'] = 'blast'
            process_params['seq'] = params['option_blast']['blast_sequence']
            if params['option_blast'].get('blast_exclude_fragments') and params['option_blast']['blast_exclude_fragments'] == 1:
                process_params['exclude_fragments'] = 1
    def get_family_params(self, params, process_params):
        if params.get('option_family') != None:
            process_params['type'] = 'family'
            process_params['family'] = params['option_family']['fam_family_name']
            process_params['uniref'] = params['option_family']['fam_use_uniref']
            if params['option_family'].get('fam_exclude_fragments') and params['option_family']['fam_exclude_fragments'] == 1:
                process_params['exclude_fragments'] = 1
    def get_fasta_params(self, params, process_params):
        if params.get('option_fasta') != None:
            process_params['type'] = 'fasta'
            fasta_file_path = None
            if params['option_fasta'].get('fasta_file') == None and params['option_fasta'].get('fasta_seq_input_text') != None:
                #TODO: write text to a file
                fasta_file_path = ''
            elif params['option_fasta'].get('fasta_file') == None:
                print("Error")#TODO: make an error here

            process_params['fasta_file'] = fasta_file_path
            if params['option_fasta'].get('fasta_exclude_fragments') and params['option_fasta']['fasta_exclude_fragments'] == 1:
                process_params['exclude_fragments'] = 1
    def get_accession_params(self, params, process_params):
        if params.get('option_accession') != None:
            process_params['type'] = 'acc'
            id_list_file = None
            if params['option_accession'].get('acc_input_file') == None and params['option_accession'].get('acc_input_list') != None:
                id_list = params['option_accession'].get('acc_input_list')
                #TODO: write this to a file
                id_list_file = ''
            elif params['option_accession'].get('acc_input_file') == None and params['option_accession'].get('acc_input_text') != None:
                acc_id_text = params['option_accession']['acc_input_text']
                #TODO: write this to a file
                id_list_file = ''
            elif params['option_accession'].get('acc_input_file') == None:
                print("Error")
                #TODO: make an error here

            process_params['id_list_file'] = id_list_file
            if params['option_accession'].get('acc_exclude_fragments') and params['option_accession']['acc_exclude_fragments'] == 1:
                process_params['exclude_fragments'] = 1

    def start_job(self):
        if not os.path.exists(self.script_file):
            #TODO: throw error
            return False

        start_job_pl = os.path.join('/bin/bash')

        process_args = [start_job_pl, self.script_file]
        process = subprocess.Popen(
            process_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = get_streams(process)

        print("### OUTPUT FROM GENERATE ######################################################################################\n")
        print(str(stdout) + "\n---------\n")
        print("### ERR\n")
        print(str(stderr) + "\n\n\n\n")

        return True

    def get_reports_path(self):
        reports_path = os.path.join(self.shared_folder, "reports")
        return reports_path

    def generate_report(self, params):

        """
        This method is where to define the variables to pass to the report.
        """
        # This path is required to properly use the template.
        reports_path = self.get_reports_path()
        utils.mkdir_p(reports_path)

        length_histogram = "length_histogram_uniprot.png"
        alignment_length = "alignment_length.png"
        percent_identity = "percent_identity.png"

        length_histogram_src = os.path.join(self.output_dir, "output", length_histogram)
        alignment_length_src = os.path.join(self.output_dir, "output", alignment_length)
        percent_identity_src = os.path.join(self.output_dir, "output", percent_identity)

        length_histogram_out = os.path.join(reports_path, length_histogram)
        alignment_length_out = os.path.join(reports_path, alignment_length)
        percent_identity_out = os.path.join(reports_path, percent_identity)

        #length_histogram_rel = os.path.join("reports", length_histogram)
        #alignment_length_rel = os.path.join("reports", alignment_length)
        #percent_identity_rel = os.path.join("reports", percent_identity)
        length_histogram_rel = length_histogram
        alignment_length_rel = alignment_length
        percent_identity_rel = percent_identity

        print(os.listdir(self.output_dir + "/output"))
        print(length_histogram_src + " --> " + length_histogram_out)

        shutil.copyfile(length_histogram_src, length_histogram_out)
        shutil.copyfile(alignment_length_src, alignment_length_out)
        shutil.copyfile(percent_identity_src, percent_identity_out)

        template_variables = {
                'length_histogram_file': length_histogram_rel,
                'alignment_length_file': alignment_length_rel,
                'percent_identity_file': percent_identity_rel,
                }

        return template_variables




class KbEstAnalysisJob(Core):

    def __init__(self, ctx, config, clients_class=None):
        super().__init__(ctx, config, clients_class)

        # self.shared_folder is defined in the Core App class.
        self.job_interface = EstAnalysisJob(config, self.shared_folder)
        self.ws_url = config['workspace-url']
        self.callback_url = config['SDK_CALLBACK_URL']
        self.dfu = DataFileUtil(self.callback_url)


    def validate_params(params):
        return EstAnalysisJob.validate_params(params)

    def create_job(self, params):
        return self.job_interface.create_job(params)

    def start_job(self):
        return self.job_interface.start_job()

    def generate_report(self, params):

        reports_path = self.job_interface.get_reports_path()
        template_variables = self.job_interface.generate_report()

        # The KBaseReport configuration dictionary
        config = dict(
            report_name = f"EfiFamilyApp_{str(uuid.uuid4())}",
            reports_path = reports_path,
            template_variables = template_variables,
            workspace_name = params["workspace_name"],
        )
        
        # Path to the Jinja template. The template can be adjusted to change
        # the report.
        template_path = os.path.join(TEMPLATES_DIR, "report.html")

        output_report = self.create_report_from_template(template_path, config)
        output_report["shared_folder"] = self.shared_folder
        print("OUTPUT REPORT\n")
        print(str(output_report) + "\n")
        return output_report



