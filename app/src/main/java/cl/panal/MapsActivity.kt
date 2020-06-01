package cl.panal

import android.content.pm.PackageManager
import android.graphics.Color
import android.location.Location
import android.os.Build
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.os.Handler
import android.view.View
import android.view.WindowManager
import androidx.core.app.ActivityCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices

import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.GoogleMap.OnMarkerClickListener
import com.google.android.gms.maps.GoogleMap.OnMapClickListener
import com.google.android.gms.maps.OnMapReadyCallback
import com.google.android.gms.maps.SupportMapFragment
import com.google.android.gms.maps.model.*
import kotlinx.android.synthetic.main.activity_maps.*

class MapsActivity : AppCompatActivity(), OnMapReadyCallback, OnMarkerClickListener, OnMapClickListener {

    private lateinit var mMap: GoogleMap

    private var polygon: Polygon? = null
    private val latLngList = ArrayList<LatLng>()

    private lateinit var lastLocation: Location
    private lateinit var fusedLocationClient: FusedLocationProviderClient

    private val mHideHandler = Handler()
    private val mHidePart2Runnable = Runnable {
        // Delayed removal of status and navigation bar

        // Note that some of these constants are new as of API 16 (Jelly Bean)
        // and API 19 (KitKat). It is safe to use them, as they are inlined
        // at compile-time and do nothing on earlier devices.
        fullscreen_content.systemUiVisibility =
            View.SYSTEM_UI_FLAG_LOW_PROFILE or
                    View.SYSTEM_UI_FLAG_FULLSCREEN or
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                    View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                    View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
    }
    private val mShowPart2Runnable = Runnable {
        // Delayed display of UI elements
        supportActionBar?.show()
        //fullscreen_content_controls.visibility = View.VISIBLE
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContentView(R.layout.activity_maps)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        // Obtain the SupportMapFragment and get notified when the map is ready to be used.
        val mapFragment = supportFragmentManager
            .findFragmentById(R.id.map) as SupportMapFragment
        mapFragment.getMapAsync(this)

        supportActionBar?.hide()

        // Schedule a runnable to remove the status and navigation bar after a delay
        mHideHandler.removeCallbacks(mShowPart2Runnable)
        mHideHandler.postDelayed(mHidePart2Runnable, 300.toLong())

        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)

    }

    /**
     * Manipulates the map once available.
     * This callback is triggered when the map is ready to be used.
     * This is where we can add markers or lines, add listeners or move the camera. In this case,
     * we just add a marker near Sydney, Australia.
     * If Google Play services is not installed on the device, the user will be prompted to install
     * it inside the SupportMapFragment. This method will only be triggered once the user has
     * installed Google Play services and returned to the app.
     */
    override fun onMapReady(googleMap: GoogleMap) {
        mMap = googleMap

        actionBar?.hide()

        mMap.uiSettings.isZoomControlsEnabled = true
        mMap.setOnMarkerClickListener(this)
        mMap.setOnMapClickListener(this)

        setUpMap()

        mMap.isMyLocationEnabled = true
        fusedLocationClient.lastLocation.addOnSuccessListener(this) { location ->
            // Got last known location. In some rare situations this can be null.
            // 3
            if (location != null) {
                lastLocation = location
                val currentLatLng = LatLng(location.latitude, location.longitude)
                mMap.animateCamera(CameraUpdateFactory.newLatLngZoom(currentLatLng, 12f))

                drawGrid(LatLng(lastLocation.latitude, lastLocation.longitude), 12f)
            }

        }
    }

    override fun onMarkerClick(p0: Marker?): Boolean {
        //
        return false
    }

    private fun drawGrid(p0: LatLng, zoomLevel: Float=0f) {
        val earthRadiusInMeters = 6371000
        var zoom =  mMap.cameraPosition.zoom
        if (zoomLevel != 0f) {
            zoom = zoomLevel
        }
        val worldWidthInDp = 256 * Math.pow(2.0, zoom.toDouble())
        val metersPerDp = earthRadiusInMeters / worldWidthInDp
        val radiusForZoomZero = 1000000.0
        val radiusZoomFactor = 1000 * radiusForZoomZero / earthRadiusInMeters
        val radius = metersPerDp * radiusZoomFactor

        drawHexagon(p0,radius, Color.argb(50, 0, 255, 0), Color.GREEN)

        val d = 2 * radius * Math.cos(Math.PI/6)
        drawHexagon(offsetBearing(p0,d,30F),radius, Color.argb(50, 0, 255, 0))
        drawHexagon(offsetBearing(p0,d,90F),radius, Color.argb(50, 0, 255, 0))
        drawHexagon(offsetBearing(p0,d,150F),radius, Color.argb(50, 0, 255, 0))
        drawHexagon(offsetBearing(p0,d,210F),radius, Color.argb(50, 0, 255, 0))
        drawHexagon(offsetBearing(p0,d,270F),radius, Color.argb(50, 0, 255, 0))
        drawHexagon(offsetBearing(p0,d,330F),radius, Color.argb(50, 0, 255, 0))

    }

    override fun onMapClick(p0: LatLng?) {
        if (p0 != null) {
            // p0 is the center of an hexagon matrix
            //val markerOptions = MarkerOptions().position(p0)
            //val marker = this.mMap.addMarker(markerOptions)
            //latLngList.add(p0)
            //markerList.add(marker)
            drawGrid(p0)
        }

    }

    private fun offsetBearing(point: LatLng, dist: Double, bearing: Float): LatLng {
        val results = FloatArray(1)
        Location.distanceBetween(point.latitude, point.longitude,
            point.latitude + 0.1, point.longitude, results)
        val latConv = results[0] * 10
        Location.distanceBetween(point.latitude, point.longitude,
            point.latitude, point.longitude + 0.1, results)
        val lngConv = results[0] * 10

        val lat = dist * Math.cos(bearing * Math.PI / 180) / latConv
        val lng = dist * Math.sin(bearing * Math.PI / 180) / lngConv

        return LatLng(point.latitude + lat, point.longitude + lng)
    }

    private fun drawHexagon(point: LatLng,
                            radius: Double,
                            fillColor: Int = Color.argb(50, 0, 255, 0),
                            strokeColor: Int = Color.GREEN) {
        val rot = 0.0

        val results = FloatArray(1)
        Location.distanceBetween(point.latitude, point.longitude,
            point.latitude + 0.1, point.longitude, results)
        val latConv = results[0] * 10
        Location.distanceBetween(point.latitude, point.longitude,
            point.latitude, point.longitude + 0.1, results)
        val lngConv = results[0] * 10

        for (i in 0 until 361 step 60) {
            val y = radius * Math.cos(i * Math.PI / 180)
            val x = radius * Math.sin(i * Math.PI / 180)

            val lng = (x * Math.cos(rot) - y * Math.sin(rot)) / lngConv
            val lat = (y * Math.cos(rot) + x * Math.sin(rot)) / latConv
            latLngList.add(LatLng(point.latitude + lat, point.longitude + lng))
        }
        val polygonOptions = PolygonOptions().addAll(latLngList).clickable(true)
        polygon = this.mMap.addPolygon(polygonOptions)
        polygon?.strokeColor = strokeColor
        polygon?.strokeWidth = 10.0F
        polygon?.fillColor = fillColor
        latLngList.clear()
    }

    private fun setUpMap() {
        if (ActivityCompat.checkSelfPermission(this,
                android.Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                arrayOf(android.Manifest.permission.ACCESS_FINE_LOCATION), LOCATION_PERMISSION_REQUEST_CODE)
            return
        }
    }

    companion object {
        private const val LOCATION_PERMISSION_REQUEST_CODE = 1
    }
}
