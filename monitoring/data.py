from .models import Samples
from deployment.models import ModelVersion



def get_baseline_data(self,model_version_id):
        # Logic to fetch baseline data samples for the model version
        model = ModelVersion.objects.get(id=model_version_id)
        samples = model.sample_data.all()
        return [sample.data for sample in samples]

def get_current_data(self,model_version_id):
        # Logic to fetch current data samples for the model version
        model = ModelVersion.objects.get(id=model_version_id)
        samples = Samples.objects.filter(model_version=model)
        return [sample.data for sample in samples]