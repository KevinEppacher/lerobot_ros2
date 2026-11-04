# How to generate Robot Description

## Requirements
```bash
pip install onshape-to-robot
```
- Export Environment Variables for Onshape API for respective terminal session
```bash
export ONSHAPE_API=https://cad.onshape.com
export ONSHAPE_API_KEY=<your_api_key>
export ONSHAPE_API_SECRET=<your_api_secret>
```
or store it in bashrc for persistent usage

```bash
echo 'export ONSHAPE_API=https://cad.onshape.com' >> ~/.bashrc
echo 'export ONSHAPE_API_KEY=<your_api_key>' >> ~/.bashrc
echo 'export ONSHAPE_API_SECRET=<your_api_secret>' >> ~/.bashrc
source ~/.bashrc
```

## 6DOF URDF Generation
```bash
cd 6dof
onshape-to-robot .
```

## 5DOF URDF Generation
```bash
cd 5dof
onshape-to-robot .
```