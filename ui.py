import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import uuid
from config import SHEET_URL

def display_calculation_results(response):
    """Display calculation results with fancy visualizations."""
    if not response or 'city_breakdown' not in response:
        return
    
    st.markdown("## 📊 Battery Swap Station Analysis Results")
    
    # Store results in session state
    st.session_state.calculation_results = response
    
    # Process the city_breakdown data
    city_data = []
    
    for city_info in response['city_breakdown'].items():
        city_name = city_info[0]
        
        # Extract vehicle types (excluding non-vehicle keys)
        vehicle_types = {}
        for key, value in city_info[1]['vehicles'].items():
            if key not in ['City']:
                vehicle_types[key] = value
        
        city_data.append({
            'city': city_name,
            'total_vehicles': city_info[1]['total_vehicles'],
            'stations_required': city_info[1]['stations_required'],
            'energy_required': city_info[1]['energy_required'],
            'swappable_energy_per_station': city_info[1]['swappable_energy_per_station'],
            'vehicle_types': vehicle_types,
            'operational_vehicles': city_info[1]['operational_vehicles']
        })
    
    df = pd.DataFrame(city_data)
    
    # Add operational vehicles calculation based on VOR
    # vor_percentage = response['parameters_used'].get('off_road_percentage', 0)
    # df['operational_vehicles'] = df['total_vehicles'] * (1 - vor_percentage / 100)
    # df['operational_vehicles'] = df['operational_vehicles'].round().astype(int)
    
    # Summary metrics
    col1, col2 = st.columns(2)
    
    with col1:
        total_stations = df['stations_required'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <h3>🏢 Total Stations</h3>
            <h2>{int(total_stations)}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_vehicles = df['total_vehicles'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <h3>🚗 Total Vehicles</h3>
            <h2>{total_vehicles:,}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # with col3:
    #     avg_utilization = response['parameters_used'].get('station_utilization', 0)
    #     st.markdown(f"""
    #     <div class="metric-card">
    #         <h3>📈 Utilization</h3>
    #         <h2>{avg_utilization}%</h2>
    #     </div>
    #     """, unsafe_allow_html=True)
    
    # with col4:
    #     vor_percentage = response['parameters_used'].get('off_road_percentage', 0)
    #     st.markdown(f"""
    #     <div class="metric-card">
    #         <h3>🔧 VOR Rate</h3>
    #         <h2>{vor_percentage}%</h2>
    #     </div>
    #     """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Create tabs for different visualizations
    tab1, tab2, tab3 = st.tabs(["📋 Data Table", "📊 Bar Chart", "🥧 Pie Chart"])
    
    with tab1:
        st.markdown("### 📋 Detailed Breakdown by City")
        
        # Prepare display dataframe
        display_df = df[['city', 'total_vehicles', 'operational_vehicles', 'stations_required', 'energy_required', 'swappable_energy_per_station']].copy()
        
        # Enhanced data table with styling
        styled_df = display_df.style.format({
            'total_vehicles': '{:,}',
            'operational_vehicles': '{:,}',
            'stations_required': '{:.0f}',
            'energy_required': '{:.2f}',
            'swappable_energy_per_station': '{:.2f}'
        }).background_gradient(subset=['stations_required'], cmap='Blues')
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Vehicle breakdown details
        st.markdown("### 🚗 Vehicle Type Breakdown")
        vehicle_breakdown_data = []
        
        for _, row in df.iterrows():
            city = row['city']
            vehicle_types = row['vehicle_types']
            for vehicle_type, count in vehicle_types.items():
                vehicle_breakdown_data.append({
                    'City': city,
                    'Vehicle Type': vehicle_type,
                    'Count': count
                })
        
        if vehicle_breakdown_data:
            vehicle_df = pd.DataFrame(vehicle_breakdown_data)
            st.dataframe(vehicle_df, use_container_width=True, height=300)
        
        # Download button
        csv = display_df.to_csv(index=False)
        random_key = str(uuid.uuid4())[:8]  # Generate a random key for download button
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"station_calculation_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv", 
            key=f"download_calculation_results_csv_{random_key}"
        )
    
    with tab2:
        st.markdown("### 📊 Stations Required by City")
        
        # Bar chart for stations required
        fig_bar = px.bar(
            df, 
            x='city', 
            y='stations_required',
            title="Battery Swap Stations Required by City",
            color='stations_required',
            color_continuous_scale='Blues',
            text='stations_required'
        )
        fig_bar.update_layout(
            xaxis_title="City",
            yaxis_title="Stations Required",
            title_x=0.5,
            height=500
        )
        fig_bar.update_traces(texttemplate='%{text:.0f}', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # Vehicle type breakdown chart
        st.markdown("### 🚗 Vehicle Distribution by City")
        
        # Prepare data for stacked bar chart
        vehicle_breakdown_for_chart = []
        all_vehicle_types = set()
        
        for _, row in df.iterrows():
            for vehicle_type in row['vehicle_types'].keys():
                all_vehicle_types.add(vehicle_type)
        
        fig_vehicles = go.Figure()
        
        for vehicle_type in all_vehicle_types:
            values = []
            for _, row in df.iterrows():
                values.append(row['vehicle_types'].get(vehicle_type, 0))
            
            fig_vehicles.add_trace(go.Bar(
                name=vehicle_type,
                x=df['city'],
                y=values,
                text=values,
                textposition='inside'
            ))
        
        fig_vehicles.update_layout(
            title="Vehicle Type Distribution by City",
            xaxis_title="City",
            yaxis_title="Number of Vehicles",
            barmode='stack',
            height=400,
            title_x=0.5
        )
        st.plotly_chart(fig_vehicles, use_container_width=True)
    
    with tab3:
        st.markdown("### 🥧 Distribution of Vehicles and Stations")
        
        # Create subplots for pie charts
        fig_pie = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "domain"}, {"type": "domain"}]],
            subplot_titles=("Vehicle Distribution", "Station Distribution")
        )
        
        # Vehicle distribution pie chart
        fig_pie.add_trace(go.Pie(
            labels=df['city'],
            values=df['total_vehicles'],
            name="Vehicles",
            hole=0.3,
            textinfo='label+percent+value'
        ), 1, 1)
        
        # Station distribution pie chart
        fig_pie.add_trace(go.Pie(
            labels=df['city'],
            values=df['stations_required'],
            name="Stations",
            hole=0.3,
            textinfo='label+percent+value'
        ), 1, 2)
        
        fig_pie.update_layout(height=500, title_text="Distribution Analysis", title_x=0.5)
        st.plotly_chart(fig_pie, use_container_width=True)
    

def create_sidebar():
    """Create enhanced sidebar with controls and info."""
    with st.sidebar:
        st.markdown('<div style="background-color: #f0f2f6; border-radius: 10px padding: 1rem">', unsafe_allow_html=True)
        
        # Clear conversation button
        if st.button("💬 New Chat", use_container_width=True):
            st.session_state.messages = []
            # st.session_state.awaiting_confirmation = False
            st.session_state.calculation_results = None
            st.rerun()
        
        # Refresh app button
        if st.button("🔄 Refresh App", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
        
        # App info
        st.markdown("### 📊 App Info")
        st.info(f"💬 Messages: {len(st.session_state.messages)}")
        
        if st.session_state.calculation_results:
            st.success("✅ Latest calculation available")
        
        st.markdown("---")
        
        # Quick actions
        st.markdown("## 📖 Read Before You Start")
        st.markdown(f"""
        - You can ask me to calculate stations (QIS) required based on vehicle data.
        - You can review or update vehicle data and assumptions in the [Google Sheet]({SHEET_URL}).
        - Specify VOR percentage, station utilization percentage, and target cities.
        """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)