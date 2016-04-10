/*==============================================================================

  Copyright (c) Laboratory for Percutaneous Surgery (PerkLab)
  Queen's University, Kingston, ON, Canada. All Rights Reserved.

  See COPYRIGHT.txt
  or http://www.slicer.org/copyright/copyright.txt for details.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  This file was originally developed by Matthew Holden, PerkLab, Queen's University
  and was supported through the Applied Cancer Research Unit program of Cancer Care
  Ontario with funds provided by the Ontario Ministry of Health and Long-Term Care

==============================================================================*/


// FiducialRegistrationWizard includes
#include "vtkSlicerFiducialRegistrationWizardLogic.h"

// MRML includes
#include "vtkMRMLLinearTransformNode.h"
#include "vtkMRMLMarkupsFiducialNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkDoubleArray.h>
#include <vtkMath.h>
#include <vtkMatrix4x4.h>
#include <vtkNew.h>
#include <vtkObjectFactory.h>
#include <vtkPCAStatistics.h>
#include <vtkSmartPointer.h>
#include <vtkTable.h>
#include <vtkThinPlateSplineTransform.h>

// STD includes
#include <cassert>
#include <sstream>


// Helper methods -------------------------------------------------------------------

double EIGENVALUE_THRESHOLD = 1e-4;

//------------------------------------------------------------------------------
void MarkupsFiducialNodeToVTKPoints( vtkMRMLMarkupsFiducialNode* markupsFiducialNode, vtkPoints* points )
{
  points->Reset();
  for ( int i = 0; i < markupsFiducialNode->GetNumberOfFiducials(); i++ )
  {
    double currentFiducial[ 3 ] = { 0, 0, 0 };
    markupsFiducialNode->GetNthFiducialPosition( i, currentFiducial );
    points->InsertNextPoint( currentFiducial );
  }
}


// Slicer methods -------------------------------------------------------------------

vtkStandardNewMacro(vtkSlicerFiducialRegistrationWizardLogic);

//------------------------------------------------------------------------------
vtkSlicerFiducialRegistrationWizardLogic::vtkSlicerFiducialRegistrationWizardLogic()
: MarkupsLogic(NULL)
{
}

//------------------------------------------------------------------------------
vtkSlicerFiducialRegistrationWizardLogic::~vtkSlicerFiducialRegistrationWizardLogic()
{
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::SetMRMLSceneInternal(vtkMRMLScene * newScene)
{
  vtkNew<vtkIntArray> events;
  events->InsertNextValue(vtkMRMLScene::NodeAddedEvent);
  events->InsertNextValue(vtkMRMLScene::NodeRemovedEvent);
  events->InsertNextValue(vtkMRMLScene::EndBatchProcessEvent);
  this->SetAndObserveMRMLSceneEventsInternal(newScene, events.GetPointer());
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::RegisterNodes()
{
  if( ! this->GetMRMLScene() )
  {
    return;
  }
  this->GetMRMLScene()->RegisterNodeClass( vtkSmartPointer< vtkMRMLFiducialRegistrationWizardNode >::New() );
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::UpdateFromMRMLScene()
{
  assert(this->GetMRMLScene() != 0);
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::OnMRMLSceneNodeAdded( vtkMRMLNode* node )
{
  if ( node == NULL || this->GetMRMLScene() == NULL )
  {
    vtkWarningMacro( "OnMRMLSceneNodeAdded: Invalid MRML scene or node" );
    return;
  }

  vtkMRMLFiducialRegistrationWizardNode* frwNode = vtkMRMLFiducialRegistrationWizardNode::SafeDownCast(node);
  if ( frwNode )
  {
    vtkDebugMacro( "OnMRMLSceneNodeAdded: Module node added." );
    vtkUnObserveMRMLNodeMacro( frwNode ); // Remove previous observers.
    vtkNew<vtkIntArray> events;
    events->InsertNextValue( vtkCommand::ModifiedEvent );
    events->InsertNextValue( vtkMRMLFiducialRegistrationWizardNode::InputDataModifiedEvent );
    vtkObserveMRMLNodeEventsMacro( frwNode, events.GetPointer() );
    
    if ( strcmp( frwNode->GetUpdateMode().c_str(), "Automatic" ) == 0 )
    {
      this->UpdateCalibration( frwNode ); // Will create modified event to update widget
    }
  }
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::OnMRMLSceneNodeRemoved( vtkMRMLNode* node )
{
  if ( node == NULL || this->GetMRMLScene() == NULL )
  {
    vtkWarningMacro( "OnMRMLSceneNodeRemoved: Invalid MRML scene or node" );
    return;
  }

  if ( node->IsA( "vtkMRMLFiducialRegistrationWizardNode" ) )
  {
    vtkDebugMacro( "OnMRMLSceneNodeRemoved" );
    vtkUnObserveMRMLNodeMacro( node );
  }
} 

//------------------------------------------------------------------------------
std::string vtkSlicerFiducialRegistrationWizardLogic::GetOutputMessage( std::string nodeID )
{
  vtkMRMLFiducialRegistrationWizardNode* node = vtkMRMLFiducialRegistrationWizardNode::SafeDownCast( this->GetMRMLScene()->GetNodeByID( nodeID.c_str() ) );
  if (node==NULL)
  {
    vtkWarningMacro("vtkSlicerFiducialRegistrationWizardLogic::GetOutputMessage failed: vtkMRMLFiducialRegistrationWizardNode with the specified ID ("<<nodeID<<") not found");
    return "";
  }
  return node->GetCalibrationStatusMessage();
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::AddFiducial( vtkMRMLLinearTransformNode* probeTransformNode )
{
  if ( probeTransformNode == NULL )
  {
    vtkWarningMacro("vtkSlicerFiducialRegistrationWizardLogic::AddFiducial failed: input transform is invalid");
    return;
  }

  vtkMRMLMarkupsFiducialNode* activeMarkupsFiducialNode = vtkMRMLMarkupsFiducialNode::SafeDownCast( this->GetMRMLScene()->GetNodeByID( this->MarkupsLogic->GetActiveListID() ) );
  if ( activeMarkupsFiducialNode == NULL )
  {
    vtkWarningMacro("vtkSlicerFiducialRegistrationWizardLogic::AddFiducial failed: no active markup list is found");
    return;
  }
  
  this->AddFiducial(probeTransformNode, activeMarkupsFiducialNode);
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::AddFiducial( vtkMRMLLinearTransformNode* probeTransformNode, vtkMRMLMarkupsFiducialNode* fiducialNode )
{
  if ( probeTransformNode == NULL )
  {
    vtkErrorMacro("vtkSlicerFiducialRegistrationWizardLogic::AddFiducial failed: input transform is invalid");
    return;
  }
  if ( fiducialNode == NULL )
  {
    vtkErrorMacro("vtkSlicerFiducialRegistrationWizardLogic::AddFiducial failed: output fiducial node is invalid");
    return;
  }
  
  vtkSmartPointer<vtkMatrix4x4> transformToWorld = vtkSmartPointer<vtkMatrix4x4>::New();
  probeTransformNode->GetMatrixTransformToWorld( transformToWorld );

  double coord[3] = { transformToWorld->GetElement( 0, 3 ), transformToWorld->GetElement( 1, 3 ), transformToWorld->GetElement( 2, 3 ) };
  fiducialNode->AddFiducialFromArray( coord );
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::UpdateCalibration( vtkMRMLNode* node )
{
  vtkMRMLFiducialRegistrationWizardNode* fiducialRegistrationWizardNode = vtkMRMLFiducialRegistrationWizardNode::SafeDownCast( node );
  if ( fiducialRegistrationWizardNode == NULL )
  {
    vtkWarningMacro("vtkSlicerFiducialRegistrationWizardLogic::UpdateCalibration failed: input node is invalid");
    return;
  }

  vtkMRMLMarkupsFiducialNode* fromMarkupsFiducialNode = fiducialRegistrationWizardNode->GetFromFiducialListNode();
  vtkMRMLMarkupsFiducialNode* toMarkupsFiducialNode = fiducialRegistrationWizardNode->GetToFiducialListNode();
  vtkMRMLTransformNode* outputTransform = fiducialRegistrationWizardNode->GetOutputTransformNode();
  std::string transformType = fiducialRegistrationWizardNode->GetRegistrationMode();

  if ( fromMarkupsFiducialNode == NULL )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'From' fiducial list is not defined." );
    return;
  }

  if ( toMarkupsFiducialNode == NULL )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'To' fiducial list is not defined." );
    return;
  }

  if ( outputTransform == NULL )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("Output transform is not defined." );
    return;
  }

  if ( fromMarkupsFiducialNode->GetNumberOfFiducials() < 3 )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'From' fiducial list has too few fiducials (minimum 3 required)." );
    return;
  }
  if ( toMarkupsFiducialNode->GetNumberOfFiducials() < 3 )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'To' fiducial list has too few fiducials (minimum 3 required)." );
    return;
  }
  if ( fromMarkupsFiducialNode->GetNumberOfFiducials() != toMarkupsFiducialNode->GetNumberOfFiducials() )
  {
    std::stringstream msg;
    msg << "Fiducial lists have unequal number of fiducials ('From' has "<<fromMarkupsFiducialNode->GetNumberOfFiducials()
      <<", 'To' has " << toMarkupsFiducialNode->GetNumberOfFiducials() << ").";
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage(msg.str());
    return;
  }

  // Convert the markupsfiducial nodes into vector of itk points
  vtkNew<vtkPoints> fromPoints;
  vtkNew<vtkPoints> toPoints;
  MarkupsFiducialNodeToVTKPoints( fromMarkupsFiducialNode, fromPoints.GetPointer() );
  MarkupsFiducialNodeToVTKPoints( toMarkupsFiducialNode, toPoints.GetPointer() );

  if ( this->CheckCollinear( fromPoints.GetPointer() ) )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'From' fiducial list has strictly collinear points.");
    return;
  }

  if ( this->CheckCollinear( toPoints.GetPointer() ) )
  {
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("'To' fiducial list has strictly collinear points.");
    return;
  }

  vtkSmartPointer<vtkAbstractTransform> transform;

  if ( transformType.compare( "Rigid" ) == 0 || transformType.compare( "Similarity" ) == 0 )
  {
    // Setup the registration
    vtkLandmarkTransform* landmarkTransform = vtkLandmarkTransform::New();
    transform = vtkSmartPointer<vtkAbstractTransform>::Take(landmarkTransform);

    landmarkTransform->SetSourceLandmarks( fromPoints.GetPointer() );
    landmarkTransform->SetTargetLandmarks( toPoints.GetPointer() );
    
    if ( transformType.compare( "Rigid" ) == 0 )
    {
      landmarkTransform->SetModeToRigidBody();
    }
    else
    {
      landmarkTransform->SetModeToSimilarity();
    }

    landmarkTransform->Update();

    // Copy the resulting transform into the outputTransform
    vtkNew<vtkMatrix4x4> calculatedTransform;
    landmarkTransform->GetMatrix( calculatedTransform.GetPointer() );
    outputTransform->SetMatrixTransformToParent( calculatedTransform.GetPointer() );
  }
  else if ( transformType.compare( "Warping" ) == 0 )
  {
    if (strcmp(outputTransform->GetClassName(), "vtkMRMLTransformNode") != 0)
    {
      vtkErrorMacro("vtkSlicerFiducialRegistrationWizardLogic::UpdateCalibration failed to save vtkThinPlateSplineTransform into transform node type "<<outputTransform->GetClassName());
      fiducialRegistrationWizardNode->SetCalibrationStatusMessage("Warping transform cannot be stored\nin linear transform node" );
      return;
    }

    // Setup the registration
    vtkThinPlateSplineTransform* tpsTransform = vtkThinPlateSplineTransform::New();
    transform = vtkSmartPointer<vtkAbstractTransform>::Take(tpsTransform);

    tpsTransform->SetSourceLandmarks( fromPoints.GetPointer() );
    tpsTransform->SetTargetLandmarks( toPoints.GetPointer() );
    tpsTransform->Update();

    // Set the resulting transform into the outputTransform
    outputTransform->SetAndObserveTransformToParent( tpsTransform );
  }
  else
  {
    vtkErrorMacro("vtkSlicerFiducialRegistrationWizardLogic::UpdateCalibration failed to set transform type: invalid transform type: "<<transformType);
    fiducialRegistrationWizardNode->SetCalibrationStatusMessage("Invalid transform type." );
    return;
  }

  double rmsError = this->CalculateRegistrationError( fromPoints.GetPointer(), toPoints.GetPointer(), transform );
  std::stringstream successMessage;
  successMessage << "Success! RMS Error: " << rmsError;
  fiducialRegistrationWizardNode->SetCalibrationStatusMessage(successMessage.str());
}

//------------------------------------------------------------------------------
double vtkSlicerFiducialRegistrationWizardLogic::CalculateRegistrationError( vtkPoints* fromPoints, vtkPoints* toPoints, vtkAbstractTransform* transform )
{
  // Transform the from points
  vtkSmartPointer<vtkPoints> transformedFromPoints = vtkSmartPointer<vtkPoints>::New();
  transform->TransformPoints( fromPoints, transformedFromPoints );

  // Calculate the RMS distance between the to points and the transformed from points
  double sumSquaredError = 0;
  for ( int i = 0; i < toPoints->GetNumberOfPoints(); i++ )
  {
    double currentToPoint[3] = { 0, 0, 0 };
    toPoints->GetPoint( i, currentToPoint );
    double currentTransformedFromPoint[3] = { 0, 0, 0 };
    transformedFromPoints->GetPoint( i, currentTransformedFromPoint );
    
    sumSquaredError += vtkMath::Distance2BetweenPoints( currentToPoint, currentTransformedFromPoint );
  }

  return sqrt( sumSquaredError / toPoints->GetNumberOfPoints() );
}

//------------------------------------------------------------------------------
bool vtkSlicerFiducialRegistrationWizardLogic::CheckCollinear( vtkPoints* points )
{
  // Initialize the x,y,z arrays for computing the PCA statistics
  vtkSmartPointer< vtkDoubleArray > xArray = vtkSmartPointer< vtkDoubleArray >::New();
  xArray->SetName( "xArray" );
  vtkSmartPointer< vtkDoubleArray > yArray = vtkSmartPointer< vtkDoubleArray >::New();
  yArray->SetName( "yArray" );
  vtkSmartPointer< vtkDoubleArray > zArray = vtkSmartPointer< vtkDoubleArray >::New();
  zArray->SetName( "zArray" );

  // Put the fiducial position values into the arrays
  double fiducialPosition[ 3 ] = { 0, 0, 0 };
  for ( int i = 0; i < points->GetNumberOfPoints(); i++ )
  {
    points->GetPoint( i, fiducialPosition );
    xArray->InsertNextValue( fiducialPosition[ 0 ] );
    yArray->InsertNextValue( fiducialPosition[ 1 ] );
    zArray->InsertNextValue( fiducialPosition[ 2 ] );
  }

  // Aggregate the arrays
  vtkSmartPointer< vtkTable > arrayTable = vtkSmartPointer< vtkTable >::New();
  arrayTable->AddColumn( xArray );
  arrayTable->AddColumn( yArray );
  arrayTable->AddColumn( zArray );
  
  /*
  // Setup the principal component analysis
  vtkSmartPointer< vtkPCAStatistics > pcaStatistics = vtkSmartPointer< vtkPCAStatistics >::New();
  pcaStatistics->SetInputData( vtkStatisticsAlgorithm::INPUT_DATA, arrayTable );
  pcaStatistics->SetColumnStatus( "xArray", 1 );
  pcaStatistics->SetColumnStatus( "yArray", 1 );
  pcaStatistics->SetColumnStatus( "zArray", 1 );
  pcaStatistics->SetDeriveOption( true );
  pcaStatistics->Update();

  // Calculate the eigenvalues
  vtkSmartPointer< vtkDoubleArray > eigenvalues = vtkSmartPointer< vtkDoubleArray >::New();
  pcaStatistics->GetEigenvalues( eigenvalues ); // Eigenvalues are largest to smallest
  
  // Test that each eigenvalues is bigger than some threshold
  int goodEigenvalues = 0;
  for ( int i = 0; i < eigenvalues->GetNumberOfTuples(); i++ )
  {
    if ( abs( eigenvalues->GetValue( i ) ) > EIGENVALUE_THRESHOLD )
    {
      goodEigenvalues++;
    }
  }

  if ( goodEigenvalues <= 1 )
  {
    return true;
  }
  */
  return false;
  
}

//------------------------------------------------------------------------------
void vtkSlicerFiducialRegistrationWizardLogic::ProcessMRMLNodesEvents( vtkObject* caller, unsigned long event, void* callData )
{
  vtkMRMLFiducialRegistrationWizardNode* frwNode = vtkMRMLFiducialRegistrationWizardNode::SafeDownCast(caller);
  if ( frwNode == NULL)
  {
    return;
  }
  
  if (event==vtkMRMLFiducialRegistrationWizardNode::InputDataModifiedEvent)
  {
    // only recompute output if the input is changed
    // (for example we do not recompute the calibration output if the computed calibration transform or status message is changed)
    if ( strcmp( frwNode->GetUpdateMode().c_str(), "Automatic" ) == 0 )
    {
      this->UpdateCalibration( frwNode ); // Will create modified event to update widget
    }
  }
}
