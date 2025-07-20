"""Example demonstrating the event and function testing framework."""

import asyncio
from tr181_comparator.event_function_tester import EventFunctionTester
from tr181_comparator.models import TR181Node, TR181Event, TR181Function, AccessLevel
from tr181_comparator.extractors import HookBasedDeviceExtractor
from tr181_comparator.hooks import RESTAPIHook, DeviceConfig


async def main():
    """Demonstrate event and function testing capabilities."""
    
    # Create a device configuration
    device_config = DeviceConfig(
        type="rest_api",
        endpoint="http://192.168.1.1/api",
        authentication={"username": "admin", "password": "password"}
    )
    
    # Create a REST API hook and device extractor
    hook = RESTAPIHook()
    device_extractor = HookBasedDeviceExtractor(hook, device_config)
    
    # Create the event and function tester
    tester = EventFunctionTester(device_extractor)
    
    # Define sample TR181 nodes with events and functions
    wifi_radio_node = TR181Node(
        path="Device.WiFi.Radio.1",
        name="Radio",
        data_type="object",
        access=AccessLevel.READ_ONLY,
        is_object=True,
        events=[
            TR181Event(
                name="ChannelChange",
                path="Device.WiFi.Radio.1.ChannelChangeEvent",
                parameters=["Device.WiFi.Radio.1.Channel", "Device.WiFi.Radio.1.SSID"],
                description="Event triggered when WiFi channel changes"
            ),
            TR181Event(
                name="StatusChange",
                path="Device.WiFi.Radio.1.StatusChangeEvent",
                parameters=["Device.WiFi.Radio.1.Status"],
                description="Event triggered when radio status changes"
            )
        ],
        functions=[
            TR181Function(
                name="SetChannel",
                path="Device.WiFi.Radio.1.SetChannel",
                input_parameters=["Device.WiFi.Radio.1.Channel"],
                output_parameters=["Device.WiFi.Radio.1.Status"],
                description="Function to set WiFi channel"
            ),
            TR181Function(
                name="Reset",
                path="Device.WiFi.Radio.1.Reset",
                input_parameters=[],
                output_parameters=["Device.WiFi.Radio.1.Status"],
                description="Function to reset WiFi radio"
            )
        ]
    )
    
    print("=== TR181 Event and Function Testing Example ===\n")
    
    try:
        # Test all events and functions associated with the node
        print("Testing events and functions for WiFi Radio node...")
        event_results, function_results = await tester.test_node_events_and_functions(wifi_radio_node)
        
        # Display event test results
        print("\n--- Event Test Results ---")
        for result in event_results:
            print(f"Event: {result.event_name}")
            print(f"  Status: {result.status.value}")
            print(f"  Message: {result.message}")
            print(f"  Parameter Validation: {'✓' if result.parameter_validation.is_valid else '✗'}")
            print(f"  Subscription Test: {'✓' if result.subscription_test else '✗'}")
            print(f"  Execution Time: {result.execution_time:.4f}s")
            if result.parameter_validation.errors:
                print(f"  Errors: {', '.join(result.parameter_validation.errors)}")
            if result.parameter_validation.warnings:
                print(f"  Warnings: {', '.join(result.parameter_validation.warnings)}")
            print()
        
        # Display function test results
        print("--- Function Test Results ---")
        for result in function_results:
            print(f"Function: {result.function_name}")
            print(f"  Status: {result.status.value}")
            print(f"  Message: {result.message}")
            print(f"  Input Validation: {'✓' if result.input_validation.is_valid else '✗'}")
            print(f"  Output Validation: {'✓' if result.output_validation.is_valid else '✗'}")
            print(f"  Execution Test: {'✓' if result.execution_test else '✗'}")
            print(f"  Execution Time: {result.execution_time:.4f}s")
            if result.input_validation.errors or result.output_validation.errors:
                all_errors = result.input_validation.errors + result.output_validation.errors
                print(f"  Errors: {', '.join(all_errors)}")
            if result.input_validation.warnings or result.output_validation.warnings:
                all_warnings = result.input_validation.warnings + result.output_validation.warnings
                print(f"  Warnings: {', '.join(all_warnings)}")
            print()
        
        # Generate and display test summary
        summary = tester.get_test_summary(event_results, function_results)
        print("--- Test Summary ---")
        print(f"Total Tests: {summary['overall']['total_tests']}")
        print(f"Passed: {summary['overall']['total_passed']}")
        print(f"Failed: {summary['overall']['total_failed']}")
        print(f"Errors: {summary['overall']['total_errors']}")
        print(f"Success Rate: {summary['overall']['success_rate']:.1%}")
        print()
        
        print("Event Statistics:")
        print(f"  Total Events: {summary['events']['total']}")
        print(f"  Passed: {summary['events']['passed']}")
        print(f"  Failed: {summary['events']['failed']}")
        print(f"  Subscription Success: {summary['events']['subscription_success']}")
        print(f"  Avg Execution Time: {summary['events']['avg_execution_time']:.4f}s")
        print()
        
        print("Function Statistics:")
        print(f"  Total Functions: {summary['functions']['total']}")
        print(f"  Passed: {summary['functions']['passed']}")
        print(f"  Failed: {summary['functions']['failed']}")
        print(f"  Execution Success: {summary['functions']['execution_success']}")
        print(f"  Avg Execution Time: {summary['functions']['avg_execution_time']:.4f}s")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Clean up
        await hook.disconnect()


async def test_individual_event_and_function():
    """Demonstrate testing individual events and functions."""
    
    print("\n=== Individual Event and Function Testing ===\n")
    
    # Create a device configuration
    device_config = DeviceConfig(
        type="rest_api",
        endpoint="http://192.168.1.1/api",
        authentication={"username": "admin", "password": "password"}
    )
    
    # Create a REST API hook and device extractor
    hook = RESTAPIHook()
    device_extractor = HookBasedDeviceExtractor(hook, device_config)
    
    # Create the event and function tester
    tester = EventFunctionTester(device_extractor)
    
    # Define individual event and function for testing
    sample_event = TR181Event(
        name="WiFiStatusChange",
        path="Device.WiFi.StatusChangeEvent",
        parameters=["Device.WiFi.Status", "Device.WiFi.SSID"],
        description="Event triggered when WiFi status changes"
    )
    
    sample_function = TR181Function(
        name="RestartWiFi",
        path="Device.WiFi.Restart",
        input_parameters=["Device.WiFi.Enable"],
        output_parameters=["Device.WiFi.Status"],
        description="Function to restart WiFi interface"
    )
    
    try:
        # Test individual event
        print("Testing individual event...")
        event_result = await tester.test_event_implementation(sample_event)
        print(f"Event '{event_result.event_name}' test result: {event_result.status.value}")
        print(f"Message: {event_result.message}")
        print()
        
        # Test individual function
        print("Testing individual function...")
        function_result = await tester.test_function_implementation(sample_function)
        print(f"Function '{function_result.function_name}' test result: {function_result.status.value}")
        print(f"Message: {function_result.message}")
        print()
        
        # Test multiple events at once
        events = [sample_event, TR181Event(
            name="ChannelChange",
            path="Device.WiFi.ChannelChangeEvent",
            parameters=["Device.WiFi.Channel"],
            description="Event for channel changes"
        )]
        
        print("Testing multiple events...")
        event_results = await tester.test_multiple_events(events)
        for result in event_results:
            print(f"  {result.event_name}: {result.status.value}")
        print()
        
        # Test multiple functions at once
        functions = [sample_function, TR181Function(
            name="SetChannel",
            path="Device.WiFi.SetChannel",
            input_parameters=["Device.WiFi.Channel"],
            output_parameters=["Device.WiFi.Status"],
            description="Function to set WiFi channel"
        )]
        
        print("Testing multiple functions...")
        function_results = await tester.test_multiple_functions(functions)
        for result in function_results:
            print(f"  {result.function_name}: {result.status.value}")
        
    except Exception as e:
        print(f"Error during individual testing: {e}")
    
    finally:
        # Clean up
        await hook.disconnect()


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
    
    # Run the individual testing example
    asyncio.run(test_individual_event_and_function())