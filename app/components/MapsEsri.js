'use client'

/** @module components/MapsEsri */

import * as React from 'react';

import '@arcgis/map-components/dist/components/arcgis-legend';
import '@arcgis/map-components/dist/components/arcgis-map';
import '@arcgis/map-components/dist/components/arcgis-zoom';
import GraphicsLayer from "@arcgis/core/layers/GraphicsLayer";
import Graphic from "@arcgis/core/Graphic";
import Map from "@arcgis/core/Map";
import MapView from "@arcgis/core/views/MapView";
import Point from "@arcgis/core/geometry/Point";
import PropTypes from 'prop-types';
import ValuePicker from "@arcgis/core/widgets/ValuePicker";
import * as reactiveUtils from "@arcgis/core/core/reactiveUtils";

import { LocationsInfoContext, UserSettingsContext } from '../serverInfo';
import { meters2feet } from '../utils';

/**
 * Returns the UI for displaying an ESRI map
 * @function
 * @param {object} center An X, Y value with the center of the area of interest
 * @param {string} mapName The ESRI name of the map to display
 * @param {array} mapChoices An array of available map display choice objects
 * @param {function} onChange Handler for when the user changes the map to display
 * @param {number} width The width of the map element (assumed to start at left:0)
 * @param {number} height The height of the map element
 * @returns {object} The rendered UI
 */
export default function MapsEsri({center, mapName, mapChoices, onChange, width, height}) {
  const locationItems = React.useContext(LocationsInfoContext);
  const userSettings = React.useContext(UserSettingsContext);  // User display settings
  const [layerCollection, setLayerCollection] = React.useState(null); // The array of layers to display
  const [generatedMap, setGeneratedMap] = React.useState(false);

  /**
   * Handle converting the locations for use with the maps
   * @function
   * @param {object} locationItems Array of locations
   * @param {string} measurementFormat A measurement format of 'feet' or 'meters'
   * @returns {Array} The array of configured elevations
   */
  function configureLocations(locationItems, measurementFormat) {
    if (measurementFormat === 'meters') {
      return locationItems;
    }

    let newLocations = JSON.parse(JSON.stringify(locationItems));

    return newLocations.map((item) => 
        ({...item, elevationProperty:Math.trunc(meters2feet(item.elevationProperty)) + 'ft'})
    );
  }

  const measurementFormat = userSettings['measurementFormat'];
  const displayLocations = React.useMemo(
            () => configureLocations(locationItems, measurementFormat), 
            [locationItems, measurementFormat]
          );

  const coordinateDisplay = userSettings['coordinatesDisplay'];
  const popupFields = React.useMemo(() => {return coordinateDisplay === 'LATLON' ?
                [ {
                    fieldName: 'nameProperty',
                    label: 'Name',
                    visible: true,
                  },
                  {
                    fieldName: 'latProperty',
                    label: 'Latitude',
                    visible: true,
                  },
                  {
                    fieldName: 'lngProperty',
                    label: 'Longitude',
                    visible: true,
                  },
                  {
                    fieldName: 'elevationProperty',
                    label: 'Elevation',
                    visible: true,
                  }
                ]
              : [ {
                  fieldName: 'nameProperty',
                  label: 'Name',
                  visible: true,
                },
                {
                  fieldName: 'utm_code',
                  label: 'UTM Code',
                  visible: true,
                },
                {
                  fieldName: 'utm_x',
                  label: 'UTM X',
                  visible: true,
                },
                {
                  fieldName: 'utm_y',
                  label: 'UTM Y',
                  visible: true,
                },
                {
                  fieldName: 'elevationProperty',
                  label: 'Elevation',
                  visible: true,
                }
              ]
            }, [coordinateDisplay]);


  /**
   * Generates the locations layer for display
   * @function
   * @returns {Array} The array of GraphicsLayer for display
   */
  const getLocationLayer = React.useCallback(() => {
    let curCollection = layerCollection || [];
    if (!layerCollection) {
      let startIdx = 0;
      while (startIdx * 100 < displayLocations.length) {
        let features = displayLocations.slice(startIdx * 100,(startIdx+1)*100).map((item, idx) => 
          new Graphic({
                  geometry: new Point({x:parseFloat(item.lngProperty),
                                       y:parseFloat(item.latProperty), 
                                       z:parseFloat(item.elevationProperty)
                                     }),
                  symbol: {
                    type: "simple-marker", // autocasts as new SimpleMarkerSymbol()
                    color: 'blue', // item.activeProperty ? "blue" : "lightgrey",
                    size: "8px",
                    outline: { // autocasts as new SimpleLineSymbol()
                      width: 0.5,
                      color: 'darkblue',// item.activeProperty ? "darkblue" : "grey"
                    }
                  },
                  attributes: {...item, objectId: idx},
                  popupTemplate: {
                    title: item.idProperty,
                    content: [{
                        type: 'fields',
                        fieldInfos: popupFields
                      }]
                  }
                })
        );

        let layer = new GraphicsLayer({graphics: features});

        curCollection.push(layer);
        startIdx++;
      }
    }
    setLayerCollection(curCollection);

    return curCollection;
  }, [layerCollection, displayLocations, popupFields])

  // When the map div is available, setup the map
  React.useLayoutEffect(() => {
    let view = null;
    let watchHandle = null;
    const mapEl = document.getElementById('viewDiv');

    if (mapEl && !generatedMap) {
      setGeneratedMap(true);
      const layers = getLocationLayer();                      // Displayed layers
      const map = new Map({basemap:mapName, layers:layers});  // Create the map of desired type

      // Get the value of the selected map for initial choice on map chooser
      const curMapName = mapChoices.find((item) => item.config.mapName === mapName);
      const curMapValue = curMapName ? curMapName.value : mapChoices[0].value;

      // Get the names of the maps and create the display control
      const collectionNames = mapChoices.map((item) => {return {label:item.name, value:item.value};});
      const valuePicker = new ValuePicker({
        visibleElements: {
          nextButton: false,
          playButton: false,
          previousButton: false
        },
        component: {
          type: "combobox", // autocasts to ValuePickerCombobox
          placeholder: "Map Type",
          items: collectionNames
        },
        values: [curMapValue],
        visible: true
      });

      // Add a watcher for when the map choice changes
      watchHandle = reactiveUtils.watch(
        () => valuePicker.values,
        (values) => onChange(values[0])
      );

      // Create the view onto the map
      view = new MapView({
        map: map,
        container: 'viewDiv',
        center: center,
        zoom: 7
      });

      // Add the map picker to the display
      view.ui.add(valuePicker, "top-right");

    }

    // Return cleanup handler
    return () => {
      watchHandle?.remove();
      view?.destroy();
    };
  }, [center, getLocationLayer, mapChoices, mapName, onChange]);

  // Return the UI
  return (
    <div id="viewDiv" style={{width:width, maxWidth:width, height:height, maxHeight:height}} >
    </div>
  );
}

MapsEsri.propTypes = {
  // An object with x/y coordinates for the map center, e.g. { x: -110.5, y: 32.1 }
  center: PropTypes.oneOfType([
    PropTypes.arrayOf(PropTypes.number),
    PropTypes.shape({
      x: PropTypes.number.isRequired,
      y: PropTypes.number.isRequired,
    }),
  ]).isRequired,

  // The ESRI basemap name string, e.g. 'topo-vector'
  mapName: PropTypes.string.isRequired,

  // Each choice needs a name for display, a value for selection,
  // and a config object containing the mapName to match against
  mapChoices: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      value: PropTypes.string.isRequired,
      config: PropTypes.shape({
        mapName: PropTypes.string.isRequired,
      }).isRequired,
    })
  ).isRequired,

  onChange: PropTypes.func.isRequired,

  width: PropTypes.number.isRequired,
  height: PropTypes.number.isRequired,
};
