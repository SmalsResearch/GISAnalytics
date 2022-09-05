# Build: podman (or docker) build -f Dockerfile -t geoconda
# might require : podman pull registry.hub.docker.com/continuumio/anaconda3
# Run: podman run --name geoconda -v ~/git/:/opt/notebooks geoconda 
#FROM continuumio/anaconda3
FROM continuumio/miniconda3

#RUN conda install -y pandas matplotlib xlrd tqdm
RUN conda install -y -c conda-forge pandas jupyter
RUN conda install -y -c conda-forge geopandas 
RUN conda install -y -c conda-forge geopy  contextily

RUN mkdir -p /opt/notebooks

COPY start_jupyter.sh /start_jupyter.sh
CMD ["/start_jupyter.sh"]  

EXPOSE 8888
