import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: 'Early Validation',
    Svg: require('@site/static/img/compileCheck.svg').default,
    description: (
      <>
        MARS detects hardware–software mismatches at compile time instead of runtime, preventing costly and hard-to-debug execution errors.
      </>
    ),
  },
  {
    title: 'Hardware Abstraction',
    Svg: require('@site/static/img/robotSwap.svg').default,
    description: (
      <>
        MARS separates logic from physical components, allowing hardware (motors, sensors, etc.) to be swapped with minimal code changes.
      </>
    ),
  },
  {
    title: 'Practical Integration',
    Svg: require('@site/static/img/ros-python.svg').default,
    description: (
      <>
        Works alongside existing tools like ROS 2 and Python, making it usable in real-world robotics systems rather than purely theoretical.
      </>
    ),
  },
];

function Feature({Svg, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
